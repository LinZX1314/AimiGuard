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
from ai.skills.drill_executor.drill_tools import get_drill_tool_definitions
from ai.skills.drill_executor import DrillState
from ai.skills.drill_executor.executor import DRILL_SYSTEM_PROMPT
from database.models import AiModel
from .helpers import (
    require_auth, ok, err, _body, _load_cfg, _save_cfg,
    _now_iso
)
from utils.logger import log as unified_log

ai_bp = Blueprint('ai', __name__)

# 运行时会话缓存（LRU 结构，防止内存泄漏）
from collections import OrderedDict

_MAX_SESSIONS = 100  # 最大缓存的会话数
_chat_sessions: OrderedDict[int, list] = OrderedDict()
_session_lock = threading.Lock()


def _get_system_context() -> str:
    """获取实时系统摘要，作为 AI 的底座背景知识"""
    from database.models import StatsModel, HFishModel
    try:
        hfish_stats = HFishModel.get_stats()

        hot_services = hfish_stats.get('service_stats', [])[:5]
        service_summary = [f"{svc['name']}({svc['count']}次)" for svc in hot_services]

        top_attackers = hfish_stats.get('ip_stats', [])[:5]
        attacker_summary = [f"{ip['ip']}({ip['count']}次)" for ip in top_attackers]

        # 通过DHCP查询在线设备数
        online_devices = 0
        try:
            from ai.tools import execute_tool
            import json
            dhcp_result = execute_tool('dhcp_query', {}, {})
            dhcp_data = json.loads(dhcp_result) if isinstance(dhcp_result, str) else dhcp_result
            if dhcp_data.get('ok'):
                online_devices = dhcp_data.get('count', 0)
        except Exception:
            pass

        ctx = [
            "### 当前系统态势摘要 ###",
            f"- DHCP在线设备数: {online_devices}",
            f"- 24小时内遭受攻击次数: {hfish_stats.get('total', 0)}",
            "",
            "### 蜜罐态势统计 ###",
            f"- 总攻击次数: {hfish_stats.get('total', 0)}",
            f"- 热门攻击服务(Top5): {', '.join(service_summary) if service_summary else '暂无数据'}",
            f"- 主要攻击来源(Top5): {', '.join(attacker_summary) if attacker_summary else '暂无数据'}",
            "",
            "你不仅是一个安服专家，还具备调用本地工具的能力。",
        ]
        return "\n".join(ctx)
    except Exception as e:
        return f"系统摘要获取失败: {e}"


def _get_history(session_id: int) -> list:
    """从内存或数据库获取会话历史（LRU 缓存）"""
    with _session_lock:
        if session_id in _chat_sessions:
            # LRU: 移到末尾表示最近使用
            _chat_sessions.move_to_end(session_id)
            return _chat_sessions[session_id]
        
        # 内存没有，尝试从 DB 加载
        history = AiModel.get_messages(session_id)
        if history:
            _chat_sessions[session_id] = history
            _chat_sessions.move_to_end(session_id)
            
            # 超过上限时删除最旧的会话
            if len(_chat_sessions) > _MAX_SESSIONS:
                _chat_sessions.popitem(last=False)
        
        return history


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
    body         = _body()
    message      = body.get('message', '').strip()
    session_id   = body.get('session_id')
    context_type = body.get('context_type')
    context_id   = body.get('context_id')

    # 检查 AI 是否启用
    cfg_now = _load_cfg()
    ai_enabled = cfg_now.get('ai', {}).get('enabled', False)
    if not ai_enabled:
        return err('AI 功能已禁用，请在设置中开启')

    if not message:
        return err('消息内容不能为空')

    # 检查是否进入演练模式（用户上传了文档）
    is_drill_mode = body.get('drill_mode', False) or ('【演练文档】' in message)
    drill_state: DrillState | None = None

    if is_drill_mode:
        drill_state = DrillState()
        drill_state.document_content = message
        unified_log('AIChat', f'进入演练模式 | doc_len={len(message)}', 'INFO')

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

    def generate():
        # 如果是新会话，流开始的第一帧直接告诉前端建立的会话 ID
        if not session_id:
            yield f"data: {json.dumps({'session_id': sid}, ensure_ascii=False)}\n\n"

        # ── 演练模式 ────────────────────────────────────────────────────────────
        if is_drill_mode and drill_state:
            yield f"data: {json.dumps({'drill_mode': True}, ensure_ascii=False)}\n\n"

            # 注入演练专用系统提示词（替换普通系统提示词）
            drill_sys_prompt = (
                "你叫玄枢指挥官，是一个专业的网络安全 AI 攻防 Agent。\n"
                "你的专有能力是：分析安全演练文档 → 智能决策执行工具 → 生成完整演练报告。\n\n"
                "## 你的可用工具（必须使用 drill_ 前缀的工具）\n"
                "- drill_analyze_document: 分析演练文档，提取目标网络、扫描范围\n"
                "- drill_plan_actions: 制定分阶段行动计划\n"
                "- drill_network_scan: 对目标网络进行资产探测和端口扫描\n"
                "- drill_web_screenshot: 对 Web 服务采集截图\n"
                "- drill_bruteforce_ssh/rdp/mysql: 弱口令检测\n"
                "- drill_honeypot_audit: 查询蜜罐攻击日志\n"
                "- drill_honeypot_stats: 获取蜜罐态势统计\n"
                "- drill_ban_ip: 封禁恶意 IP\n"
                "- drill_generate_report: 生成完整演练报告（必须最后调用）\n"
                "- drill_get_status: 查询当前演练进度\n\n"
                "## 正确的工作流\n"
                "1. 立即调用 drill_analyze_document 分析演练文档\n"
                "2. 调用 drill_plan_actions 制定行动计划\n"
                "3. 按计划执行：先网络扫描 → 再服务枚举 → 再漏洞检测\n"
                "4. 发现 Web 服务立即截图\n"
                "5. 发现 SSH/RDP/MySQL 服务立即尝试弱口令\n"
                "6. 定期查询蜜罐日志，发现攻击者立即封禁\n"
                "7. 所有步骤完成后调用 drill_generate_report\n"
                "8. 最多执行 30 步，遇到 drill_generate_report 立即结束\n\n"
                "## 重要原则\n"
                "- 发现漏洞必须记录（severity: critical/high/medium/info）\n"
                "- 弱口令发现是 critical 级别，必须在 finding 中记录\n"
                "- 扫描结果中的可疑 IP 要主动尝试封禁\n"
                "- 报告要用中文，包含所有发现的问题\n\n"
                "## 背景信息\n"
                f"{_get_system_context()}\n\n"
                "现在请开始分析演练文档并执行安全演练！"
            )

            # 清除旧系统消息，插入演练专用系统消息
            if history and history[0].get('role') == 'system':
                history[0] = {'role': 'system', 'content': drill_sys_prompt, 'ts': _now_iso()}
            else:
                history.insert(0, {'role': 'system', 'content': drill_sys_prompt, 'ts': _now_iso()})

            all_tools = AI_TOOLS + get_drill_tool_definitions()

            for chunk in _run_agent_loop(history, all_tools, cfg_now, sid, drill_state, True):
                yield f"data: {chunk}\n\n"

            yield f"data: {json.dumps({'done': True, 'session_id': sid}, ensure_ascii=False)}\n\n"
            return

        # ── 普通对话模式 ────────────────────────────────────────────────────────
        full_reply = []
        tool_calls_received = []
        # 普通对话也传入 drill 工具，AI 智能判断何时使用
        all_tools_normal = AI_TOOLS + get_drill_tool_definitions()

        # 第一轮：LLM 判断内容或调用工具
        for chunk, error, tool_call in stream_openai_chat_with_tools(
            build_openai_messages(history),
            cfg_now,
            tools=all_tools_normal
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
            AiModel.save_message(sid, 'assistant', res_content)
            yield f"data: {json.dumps({'done': True, 'session_id': sid}, ensure_ascii=False)}\n\n"
            return

        # 检查是否需要进入演练模式（AI 智能调用了 drill 工具）
        has_drill_tools = any(tc['name'].startswith('drill_') for tc in tool_calls_received)
        if has_drill_tools and not is_drill_mode:
            drill_state = DrillState()
            drill_state.document_content = message
            yield f"data: {json.dumps({'drill_mode': True}, ensure_ascii=False)}\n\n"

        # 执行工具并处理（支持多轮循环）
        for chunk in _run_agent_loop(history, all_tools_normal, cfg_now, sid, drill_state, has_drill_tools or is_drill_mode):
            yield f"data: {chunk}\n\n"
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


def _run_agent_loop(history: list, tools: list, cfg: dict, sid: int,
                    drill_state: DrillState | None, is_drill_mode: bool):
    """
    多轮 Agent 循环（生成器）。每次 yield 返回完整的 SSE data 行。
    LLM决定工具 → 执行 → 结果给LLM → 继续直到完成
    """
    from ai.skills.drill_executor.bruteforce import run_bruteforce as drill_bruteforce

    max_steps = 30
    step_count = 0

    def _execute_tool(tool_name: str, arguments: dict) -> str:
        """统一工具执行入口"""
        import json as _json
        from datetime import datetime as _dt

        if tool_name.startswith('drill_'):
            # ── 演练专用工具 ────────────────────────────────────────────────
            if tool_name == 'drill_analyze_document':
                doc_content = arguments.get('document_content', '')
                if not doc_content:
                    doc_content = drill_state.document_content if drill_state else ''
                if not doc_content:
                    return _json.dumps({'ok': False, 'error': '文档内容为空'})
                if drill_state:
                    drill_state.document_content = doc_content
                    # 智能提取关键信息
                    import re
                    targets = re.findall(r'\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?', doc_content)
                    services = re.findall(r'(?:SSH|RDP|MySQL|SMB|MSSQL|PostgreSQL|Redis|SMTP|HTTP|HTTPS|Web)', doc_content, re.IGNORECASE)
                    analysis = f"文档分析完成。提取到 {len(targets)} 个目标， {len(services)} 种服务类型。"
                    if targets:
                        analysis += f" 目标：{', '.join(set(targets[:5]))}"
                    if services:
                        analysis += f" 服务：{', '.join(set(services))}"
                    drill_state.document_summary = analysis
                return _json.dumps({
                    'ok': True,
                    'message': f'文档分析完成。提取到目标网络，正在制定行动计划...',
                    'target_count': len(set(re.findall(r'\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?', doc_content))),
                    'document_summary': analysis if drill_state else '',
                })

            if tool_name == 'drill_plan_actions':
                if drill_state:
                    plan = (
                        "## 行动计划\n\n"
                        "### 阶段一：资产发现（使用 drill_network_scan）\n"
                        "- 对目标网络进行 Ping 探测和端口扫描\n"
                        "- 识别存活主机和开放端口\n\n"
                        "### 阶段二：服务枚举（使用 drill_web_screenshot）\n"
                        "- 对发现的 Web 服务采集截图\n"
                        "- 记录管理后台、登录页面\n\n"
                        "### 阶段三：漏洞检测（使用 drill_bruteforce_*）\n"
                        "- 对 SSH(22)/RDP(3389)/MySQL(3306) 尝试弱口令检测\n"
                        "- 发现的弱口令记录为 critical 级别 finding\n\n"
                        "### 阶段四：蜜罐审计（使用 drill_honeypot_audit）\n"
                        "- 查询攻击日志，发现攻击者立即封禁\n\n"
                        "### 阶段五：报告生成（使用 drill_generate_report）\n"
                        "- 汇总所有发现，生成完整演练报告"
                    )
                    drill_state.action_plan = plan
                return _json.dumps({'ok': True, 'message': '行动计划已生成，正在开始执行...', 'plan': plan if drill_state else ''})

            if tool_name == 'drill_network_scan':
                target = arguments.get('target', '')
                if not target:
                    return _json.dumps({'ok': False, 'error': '缺少扫描目标'})
                if drill_state:
                    drill_state.target_network = target
                result = _json.loads(execute_tool('run_fscan', {
                    'target': target,
                    'port': arguments.get('port', '21,22,23,80,81,135,139,443,445,1433,3306,5432,6379,8080,8443'),
                }, cfg))
                if drill_state and result.get('ok'):
                    drill_state.add_scan_result({'time': _dt.now().strftime('%Y-%m-%d %H:%M:%S'), 'target': target, 'result': result})
                return _json.dumps(result)

            if tool_name == 'drill_web_screenshot':
                url = arguments.get('url', '')
                ip = arguments.get('ip', '')
                port = arguments.get('port', 80)
                if not url or not ip:
                    return _json.dumps({'ok': False, 'error': '缺少参数'})
                result = _json.loads(execute_tool('take_screenshot', {'url': url, 'ip': ip, 'port': port}, cfg))
                if drill_state and result.get('ok'):
                    drill_state.add_screenshot_result({'time': _dt.now().strftime('%Y-%m-%d %H:%M:%S'), 'ip': ip, 'port': port, 'url': url, 'screenshot_url': result.get('screenshot_url', '')})
                return _json.dumps(result)

            if tool_name in ('drill_bruteforce_ssh', 'drill_bruteforce_rdp', 'drill_bruteforce_mysql'):
                target_ip = arguments.get('target_ip', '')
                if not target_ip:
                    return _json.dumps({'ok': False, 'error': '缺少目标IP'})
                result = drill_bruteforce(tool_name, target_ip, arguments.get('port'))
                if drill_state and result.get('ok'):
                    drill_state.add_bruteforce_result({'time': _dt.now().strftime('%Y-%m-%d %H:%M:%S'), 'tool': tool_name, 'target': target_ip, 'result': result})
                return _json.dumps(result)

            if tool_name == 'drill_honeypot_audit':
                result = _json.loads(execute_tool('get_honeypot_logs', {
                    'service_name': arguments.get('service_name'),
                    'limit': arguments.get('limit', 50),
                }, cfg))
                if drill_state and result.get('ok'):
                    drill_state.add_honeypot_result({'time': _dt.now().strftime('%Y-%m-%d %H:%M:%S'), 'service': arguments.get('service_name') or '全部', 'count': result.get('总数', 0), 'records': result.get('攻击记录', [])})
                return _json.dumps(result)

            if tool_name == 'drill_honeypot_stats':
                result = _json.loads(execute_tool('get_honeypot_stats', {}, cfg))
                return _json.dumps(result)

            if tool_name == 'drill_ban_ip':
                target_ip = arguments.get('target_ip', '')
                if not target_ip:
                    return _json.dumps({'ok': False, 'error': '缺少目标IP'})
                result = _json.loads(execute_tool('switch_acl_config', {
                    'action': 'ban',
                    'target_ip': target_ip,
                    'description': arguments.get('reason', '演练中发现的可疑IP'),
                }, cfg))
                return _json.dumps(result)

            if tool_name == 'drill_generate_report':
                if not drill_state:
                    return _json.dumps({'ok': False, 'error': '演练状态不存在'})
                report = _generate_drill_report(drill_state)
                drill_state.report_content = report
                drill_state.is_complete = True
                return _json.dumps({'ok': True, 'report': report, 'summary': drill_state.get_exec_summary()})

            if tool_name == 'drill_get_status':
                if drill_state:
                    return _json.dumps({'ok': True, **drill_state.to_dict()})
                return _json.dumps({'ok': True})

            return _json.dumps({'ok': False, 'error': f'未知工具: {tool_name}'})

        # 系统工具
        return execute_tool(tool_name, arguments, cfg)

    # ─── Agent 主循环 ──────────────────────────────────────────────────────
    while step_count < max_steps:
        step_count += 1

        # 发送步骤开始
        yield json.dumps({'drill_step': {
            'step': step_count,
            'status': 'thinking',
            'message': f'🤔 AI 正在思考下一步... (第 {step_count}/{max_steps} 步)',
        }})

        tool_calls = []
        text_chunks = []

        # LLM 决策
        for chunk, error, tool_call in stream_openai_chat_with_tools(
            build_openai_messages(history), cfg, tools=tools
        ):
            if error:
                yield json.dumps({'error': error})
                return
            if chunk:
                text_chunks.append(chunk)
                yield json.dumps({'content': chunk})
            if tool_call:
                tool_calls.append(tool_call)

        response_text = ''.join(text_chunks)
        if response_text:
            history.append({'role': 'assistant', 'content': response_text})

        # 无工具调用则结束
        if not tool_calls:
            unified_log('AIChat', f'Agent循环结束（无更多工具调用）| 共 {step_count} 步', 'INFO')
            break

        # 保存 assistant tool_call 消息
        history.append({
            'role': 'assistant',
            'content': response_text or None,
            'tool_calls': [{
                'id': tc['id'],
                'type': 'function',
                'function': {'name': tc['name'], 'arguments': json.dumps(tc['arguments'], ensure_ascii=False)},
            } for tc in tool_calls]
        })

        # ─── 执行工具 ────────────────────────────────────────────────────────
        for tc in tool_calls:
            tool_name = tc['name']
            tool_args = tc['arguments']

            # 发送工具调用开始
            yield json.dumps({'tool_call': {
                'id': tc['id'],
                'name': tool_name,
                'arguments': tool_args,
                'status': 'executing',
            }})

            # 执行工具
            res = _execute_tool(tool_name, tool_args)

            # 发送给前端（截断过长结果）
            try:
                res_json = json.loads(res)
                display = res[:800] + '...' if len(res) > 800 else res
            except Exception:
                display = res[:800] + '...' if len(res) > 800 else res

            yield json.dumps({'tool_result': {
                'id': tc['id'],
                'name': tool_name,
                'result': display,
                'full_result': res,
                'status': 'done',
            }})

            # 保存工具结果
            history.append({'role': 'tool', 'tool_call_id': tc['id'], 'content': res, 'ts': _now_iso()})

            # 演练模式：检查是否生成报告
            if is_drill_mode and drill_state and tool_name == 'drill_generate_report':
                try:
                    report_res = json.loads(res)
                    if report_res.get('ok'):
                        yield json.dumps({'drill_complete': {
                            'report': report_res.get('report', ''),
                            'summary': drill_state.get_exec_summary(),
                            'findings_count': len(drill_state.findings),
                        }})
                except Exception:
                    pass

        # 检查演练是否已结束
        if is_drill_mode and drill_state and drill_state.is_complete:
            yield json.dumps({'drill_complete': {
                'report': drill_state.report_content,
                'summary': drill_state.get_exec_summary(),
                'findings_count': len(drill_state.findings),
            }})
            break

    # 保存最后一条 assistant 消息
    if history and history[-1].get('role') == 'assistant':
        try:
            AiModel.save_message(sid, 'assistant', history[-1].get('content') or '')
        except Exception:
            pass



def _generate_drill_report(state: DrillState) -> str:
    """生成演练 Markdown 报告"""
    from datetime import datetime

    critical = [f for f in state.findings if f.get('severity') == 'critical']
    high = [f for f in state.findings if f.get('severity') == 'high']
    medium = [f for f in state.findings if f.get('severity') == 'medium']
    info = [f for f in state.findings if f.get('severity') == 'info']

    report = f"""# 🛡️ 安全演练报告

> **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> **目标网络**: {state.target_network or '未指定'}

---

## 执行摘要

```
{state.get_exec_summary()}
```

---

## 安全问题发现

| 严重级别 | 数量 |
|---------|------|
| 🔴 严重 | {len(critical)} |
| 🟠 高危 | {len(high)} |
| 🟡 中危 | {len(medium)} |
| ℹ️ 信息 | {len(info)} |

"""

    if critical:
        report += "### 🔴 严重风险\n\n"
        for f in critical:
            report += f"- **{f.get('type', '未知').upper()}** | `{f.get('ip', 'N/A')}:{f.get('port', 'N/A')}` | {f.get('description', 'N/A')}\n"

    if high:
        report += "### 🟠 高危问题\n\n"
        for f in high:
            report += f"- **{f.get('type', '未知').upper()}** | `{f.get('ip', 'N/A')}:{f.get('port', 'N/A')}` | {f.get('vuln', f.get('description', 'N/A'))}\n"

    report += f"""
---

## 扫描结果

共执行 **{len(state.scan_results)}** 次网络扫描，发现 **{sum(r.get('result', {}).get('发现主机', 0) for r in state.scan_results)}** 台主机

"""

    for sr in state.scan_results:
        r = sr.get('result', {})
        hosts = r.get('主机列表', [])
        if hosts:
            report += f"**目标 {sr.get('target', 'N/A')}** — {r.get('发现主机', 0)} 台主机\n"
            for h in hosts[:10]:
                report += f"- `{h.get('ip', 'N/A')}` : {h.get('ports', 'N/A')}\n"

    if state.screenshot_results:
        report += f"""
---

## Web 截图

共采集 **{len(state.screenshot_results)}** 张截图

| IP | 端口 | URL |
|----|------|-----|
"""
        for sr in state.screenshot_results:
            report += f"| `{sr.get('ip', 'N/A')}` | {sr.get('port', 'N/A')} | {sr.get('url', 'N/A')} |\n"

    vulnerable_bf = [r for r in state.bruteforce_results if r.get('result', {}).get('vulnerable')]
    if vulnerable_bf:
        report += f"""
---

## 🔴 弱口令检测 — 发现 {len(vulnerable_bf)} 个风险！

"""
        for r in vulnerable_bf:
            result = r.get('result', {})
            for cred in result.get('vulnerable_creds', []):
                report += f"- **{r.get('tool', '').upper()}** `{r.get('target', '')}` → 弱口令: `{cred.get('username')}` / `{cred.get('password')}`\n"

    if state.ban_records:
        report += """
---

## 已封禁 IP

"""
        for br in state.ban_records:
            report += f"- 🛡️ `{br.get('ip', 'N/A')}` — {br.get('reason', '')}\n"

    report += f"""
---

## 修复建议

"""
    for f in critical:
        report += f"1. **紧急** — 修复 `{f.get('ip', '')}:{f.get('port', '')}` {f.get('type', '')} 问题\n"
    for f in high[:5]:
        report += f"2. **高危** — 处理 `{f.get('ip', '')}:{f.get('port', '')}` {f.get('vuln', f.get('description', ''))}\n"

    report += """
---

*本报告由玄枢指挥官 AI 自动生成 | 玄枢·AI安全系统*
"""
    return report


def new_chat():
    """清空缓存，强制重新从数据库加载"""
    _chat_sessions.clear()
