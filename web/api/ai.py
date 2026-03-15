"""
AI Module - AI Chat endpoints（含上下文/会话持久化与 Tool Use 支持）
"""
import json
import threading
from flask import Blueprint, request, g, Response, stream_with_context
from ai import (
    build_openai_messages,
    call_openai_chat_completion,
    stream_openai_chat_completion,
    stream_openai_chat_with_tools,
    AI_TOOLS,
    execute_tool,
)
from database.models import AiModel
from .helpers import (
    require_auth, ok, err, _body, _load_cfg, _save_cfg,
    _now_iso
)
from utils.logger import log as unified_log

ai_bp = Blueprint('ai', __name__)

# 运行时会话缓存（LRU 结构或简单字典，用于加速当前对话）
_chat_sessions: dict[int, list] = {}
_session_lock = threading.Lock()


def _get_system_context() -> str:
    """获取实时系统摘要，作为 AI 的底座背景知识"""
    from database.models import StatsModel, HFishModel, VulnModel
    try:
        summary = StatsModel.get_dashboard_summary()
        hfish_stats = HFishModel.get_stats()
        vuln_stats = VulnModel.get_vuln_stats()
        
        ctx = [
            "### 当前系统态势摘要 ###",
            f"- 在线设备数: {summary.get('online_devices', 0)}",
            f"- 存疑/有风险设备: {vuln_stats.get('vulnerable_devices', 0)}",
            f"- 24小时内遭受攻击次数: {summary.get('attacks_24h', 0)}",
            f"- 最近扫描时间: {summary.get('last_scan', '尚未扫描')}",
            f"- 高危威胁统计: " + ", ".join([f"{s['level']}: {s['count']}" for s in hfish_stats.get('threat_stats', [])]),
            "\n你不仅是一个安服专家，还具备调用本地工具的能力。"
        ]
        return "\n".join(ctx)
    except Exception as e:
        return f"系统摘要获取失败: {e}"


def _get_history(session_id: int) -> list:
    """从内存或数据库获取会话历史"""
    with _session_lock:
        if session_id in _chat_sessions:
            return _chat_sessions[session_id]
        
        # 内存没有，尝试从 DB 加载
        history = AiModel.get_messages(session_id)
        if history:
            _chat_sessions[session_id] = history
            return history
    return []


# ──────────────────────────────────────────────────────────────────────────────
# 路由接口
# ──────────────────────────────────────────────────────────────────────────────

@ai_bp.route('/sessions', methods=['GET'])
@require_auth
def ai_sessions():
    """从数据库获取持久化的会话列表"""
    sessions = AiModel.get_sessions()
    return ok(sessions)


@ai_bp.route('/sessions/<int:session_id>/messages', methods=['GET'])
@require_auth
def ai_session_messages(session_id: int):
    """获取指定会话的历史记录（含持久化数据）"""
    history = _get_history(session_id)
    # 过滤掉系统消息，只返回给前端对话部分
    out = [m for m in history if m.get('role') != 'system']
    return ok(out)


@ai_bp.route('/sessions/<int:session_id>', methods=['DELETE'])
@require_auth
def ai_session_delete(session_id: int):
    """从数据库和缓存中删除会话"""
    AiModel.delete_session(session_id)
    with _session_lock:
        _chat_sessions.pop(session_id, None)
    return ok()


@ai_bp.route('/chat/stream', methods=['POST'])
@require_auth
def ai_chat_stream():
    """
    AI 聊天流式接口（增加持久化深度和上下文感知）
    """
    unified_log('AIChat', f'Stream Request from={request.remote_addr}', 'INFO')

    body         = _body()
    message      = body.get('message', '').strip()
    session_id   = body.get('session_id')
    context_type = body.get('context_type')
    context_id   = body.get('context_id')

    if not message:
        return err('消息内容不能为空')

    # 1. 确定会话 ID
    if session_id:
        sid = int(session_id)
        history = _get_history(sid)
    else:
        # 创建新会话
        title = message[:20] + "..." if len(message) > 20 else message
        sid = AiModel.create_session(title=title, context_type=context_type, context_id=context_id)
        history = []
        
        # 注入初始上下文
        sys_info = _get_system_context()
        if context_type and context_id:
            sys_info += f"\n当前焦点上下文: {context_type} = {context_id}"
            if context_type == 'host':
                from database.models import NmapModel
                host = NmapModel.get_host_by_ip(context_id)
                if host: sys_info += f"\n详细资产数据: {json.dumps(host, ensure_ascii=False)}"
        
        history.append({'role': 'system', 'content': f"你叫玄枢指挥官，你是一个专业的网络安全助手。背景：\n{sys_info}", 'ts': _now_iso()})
        with _session_lock:
            _chat_sessions[sid] = history

    # 2. 保存并追加用户消息
    history.append({'role': 'user', 'content': message, 'ts': _now_iso()})
    AiModel.save_message(sid, 'user', message)
    
    cfg_now = _load_cfg()

    def generate():
        # 如果是新会话，流开始的第一帧直接告诉前端建立的会话 ID
        if not session_id:
            yield f"data: {json.dumps({'session_id': sid}, ensure_ascii=False)}\n\n"

        full_reply = []
        tool_calls_received = []

        # 第一轮：LLM 判断内容或调用工具
        for chunk, error, tool_call in stream_openai_chat_with_tools(
            build_openai_messages(history),
            cfg_now,
            tools=AI_TOOLS
        ):
            if error:
                yield f"data: {json.dumps({'error': error}, ensure_ascii=False)}\n\n"
                return
            if chunk:
                full_reply.append(chunk)
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            if tool_call:
                tool_calls_received.append(tool_call)
                yield f"data: {json.dumps({'tool_call': tool_call}, ensure_ascii=False)}\n\n"

        # 如果没有工具调用，保存回复并结束
        if not tool_calls_received:
            res_content = "".join(full_reply)
            history.append({'role': 'assistant', 'content': res_content, 'ts': _now_iso()})
            try:
                AiModel.save_message(sid, 'assistant', res_content)
                print(f"[AIChat] 保存助手消息成功, sid={sid}, content_len={len(res_content)}")
            except Exception as e:
                print(f"[AIChat] 保存助手消息失败: {e}")
            yield f"data: {json.dumps({'done': True, 'session_id': sid}, ensure_ascii=False)}\n\n"
            return

        # 执行工具并处理
        # assistant 消息持久化（包含 tool_calls）
        assistant_tc_msg = {
            'role': 'assistant',
            'content': "".join(full_reply) or None,
            'tool_calls': [
                {
                    'id': tc['id'],
                    'type': 'function',
                    'function': {'name': tc['name'], 'arguments': json.dumps(tc['arguments'], ensure_ascii=False)}
                } for tc in tool_calls_received
            ]
        }
        history.append(assistant_tc_msg)
        AiModel.save_message(sid, 'assistant', assistant_tc_msg['content'], tool_calls=assistant_tc_msg['tool_calls'])

        for tc in tool_calls_received:
            res = execute_tool(tc['name'], tc['arguments'], cfg_now)
            yield f"data: {json.dumps({'tool_result': res[:1000] + '...' if len(res)>1000 else res}, ensure_ascii=False)}\n\n"
            
            # 保存工具执行结果
            history.append({'role': 'tool', 'tool_call_id': tc['id'], 'content': res, 'ts': _now_iso()})
            AiModel.save_message(sid, 'tool', res)

        # 第二轮：整合结果
        second_reply = []
        for chunk, error in stream_openai_chat_completion(build_openai_messages(history), cfg_now):
            if error:
                yield f"data: {json.dumps({'error': error}, ensure_ascii=False)}\n\n"
                return
            if chunk:
                second_reply.append(chunk)
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"

        final_content = "".join(second_reply)
        history.append({'role': 'assistant', 'content': final_content, 'ts': _now_iso()})
        try:
            AiModel.save_message(sid, 'assistant', final_content)
            print(f"[AIChat] 保存最终助手消息成功, sid={sid}, content_len={len(final_content)}")
        except Exception as e:
            print(f"[AIChat] 保存最终助手消息失败: {e}")
        yield f"data: {json.dumps({'done': True, 'session_id': sid}, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'X-Content-Type-Options': 'nosniff',
            'Content-Encoding': 'identity',
            'Connection': 'keep-alive',
        }
    )


def new_chat():
    """清空缓存，强制重新从数据库加载"""
    _chat_sessions.clear()
