"""
AI Module - AI Chat endpoints（含上下文/会话持久化与 Tool Use 支持）
"""

import json
import base64
import threading
from flask import Blueprint, request, g, Response, stream_with_context
from ai import (
    build_openai_messages,
    stream_openai_chat_with_tools,
    AI_TOOLS,
    execute_tool,
)
from ai.skills.drill_executor.drill_tools import get_drill_tool_definitions
from ai.skills.drill_executor import DrillState
from ai.skills.drill_executor.executor import DRILL_SYSTEM_PROMPT, create_drill_stream
from database.models import AiModel
from .helpers import require_auth, ok, err, _body, _load_cfg, _save_cfg, _now_iso
from utils.logger import log as unified_log

ai_bp = Blueprint("ai", __name__)

# 运行时会话缓存（LRU 结构，防止内存泄漏）
from collections import OrderedDict

_MAX_SESSIONS = 100  # 最大缓存的会话数
_chat_sessions: OrderedDict[int, list] = OrderedDict()
_session_lock = threading.Lock()

_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".log",
    ".csv",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".js",
    ".ts",
    ".py",
    ".java",
    ".sh",
    ".bat",
}


def _is_text_like_file(filename: str, mimetype: str) -> bool:
    if (mimetype or "").startswith("text/"):
        return True
    lower = (filename or "").lower()
    return any(lower.endswith(ext) for ext in _TEXT_EXTENSIONS)


def _parse_chat_payload():
    """兼容 JSON 与 multipart/form-data（原生文件上传）请求。"""
    content_type = (request.content_type or "").lower()
    if "multipart/form-data" in content_type:
        body = {
            "message": (request.form.get("message") or "").strip(),
            "session_id": request.form.get("session_id"),
            "context_type": request.form.get("context_type"),
            "context_id": request.form.get("context_id"),
            "drill_mode": str(request.form.get("drill_mode", "")).strip().lower()
            in ("1", "true", "yes", "on"),
        }
        files = request.files.getlist("files")
        return body, files

    return _body(), []


def _normalize_uploaded_files(message: str, files: list):
    """将上传文件整理成：1) 持久化文本 2) OpenAI 多模态内容。"""
    if not files:
        return message, None

    safe_message = (message or "").strip() or "请分析我上传的文件/图片。"
    openai_content = [{"type": "text", "text": safe_message}]

    file_summaries = []
    text_blocks = []

    for storage in files[:6]:
        if not storage:
            continue

        filename = (getattr(storage, "filename", None) or "unnamed").strip()
        mimetype = (
            getattr(storage, "mimetype", None) or "application/octet-stream"
        ).strip()
        raw = storage.read() or b""
        storage.stream.seek(0)

        if not raw:
            file_summaries.append(f"- {filename}: 空文件")
            continue

        size_kb = max(1, len(raw) // 1024)
        file_summaries.append(f"- {filename} ({mimetype}, {size_kb}KB)")

        if mimetype.startswith("image/"):
            # 后端原生接收文件，并在服务端转换为模型可读的 image_url
            b64 = base64.b64encode(raw).decode("utf-8")
            openai_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mimetype};base64,{b64}"},
                }
            )
            continue

        if _is_text_like_file(filename, mimetype):
            try:
                decoded = raw.decode("utf-8")
            except UnicodeDecodeError:
                decoded = raw.decode("gbk", errors="ignore")

            clipped = decoded[:80_000]
            if len(decoded) > 80_000:
                clipped += "\n\n...[文件内容过长，已截断]"
            text_blocks.append(f"【文件内容：{filename}】\n{clipped}")
            continue

    summary_text = "[已上传文件]\n" + "\n".join(file_summaries)
    openai_content.append({"type": "text", "text": summary_text})

    if text_blocks:
        openai_content.append({"type": "text", "text": "\n\n".join(text_blocks)})

    persisted_message = f"{safe_message}\n\n{summary_text}"
    return persisted_message, openai_content


def _get_system_context() -> str:
    """获取实时系统摘要，作为 AI 的底座背景知识"""
    from database.models import StatsModel, HFishModel

    try:
        hfish_stats = HFishModel.get_stats()

        hot_services = hfish_stats.get("service_stats", [])[:5]
        service_summary = [f"{svc['name']}({svc['count']}次)" for svc in hot_services]

        top_attackers = hfish_stats.get("ip_stats", [])[:5]
        attacker_summary = [f"{ip['ip']}({ip['count']}次)" for ip in top_attackers]

        # 通过DHCP查询在线设备数
        online_devices = 0
        try:
            from ai.tools import execute_tool
            import json

            dhcp_result = execute_tool("dhcp_query", {}, {})
            dhcp_data = (
                json.loads(dhcp_result) if isinstance(dhcp_result, str) else dhcp_result
            )
            if dhcp_data.get("ok"):
                online_devices = dhcp_data.get("count", 0)
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


@ai_bp.route("/sessions", methods=["GET"])
@require_auth
def ai_sessions():
    """从数据库获取持久化的会话列表"""
    sessions = AiModel.list_sessions()
    return ok(sessions)


@ai_bp.route("/reports", methods=["GET"])
@require_auth
def ai_reports():
    """从数据库获取所有已生成的演练报告"""
    reports = AiModel.get_reports()
    return ok(reports)


@ai_bp.route("/sessions/<int:session_id>/messages", methods=["GET"])
@require_auth
def ai_session_messages(session_id: int):
    """获取指定会话的历史记录（含持久化数据）"""
    history = _get_history(session_id)
    # 过滤掉系统消息，只返回给前端对话部分
    out = [m for m in history if m.get("role") != "system"]
    return ok(out)


@ai_bp.route("/sessions/<int:session_id>", methods=["DELETE"])
@require_auth
def ai_session_delete(session_id: int):
    """从数据库和缓存中删除会话"""
    AiModel.delete_session(session_id)
    with _session_lock:
        _chat_sessions.pop(session_id, None)
    return ok()


@ai_bp.route("/chat/stream", methods=["POST"])
@require_auth
def ai_chat_stream():
    """
    AI 聊天流式接口（增加持久化深度和上下文感知）
    """
    body, uploaded_files = _parse_chat_payload()
    message = body.get("message", "").strip()
    session_id = body.get("session_id")
    context_type = body.get("context_type")
    context_id = body.get("context_id")

    unified_log(
        "AIChat",
        f"收到请求 | message={message[:50] if message else 'empty'}... | files={len(uploaded_files)}",
        "INFO",
    )

    message, openai_content = _normalize_uploaded_files(message, uploaded_files)

    unified_log(
        "AIChat",
        f"处理后 | message={message[:50] if message else 'empty'}... | openai_content={'有' if openai_content else '无'}",
        "INFO",
    )

    # 检查 AI 是否启用
    cfg_now = _load_cfg()
    ai_enabled = cfg_now.get("ai", {}).get("enabled", False)
    if not ai_enabled:
        return err("AI 功能已禁用，请在设置中开启")

    if not message:
        return err("消息内容不能为空")

    # 检查是否进入演练模式（只有上传图片时才进入）
    has_image = uploaded_files and any(
        f.mimetype.startswith("image/") for f in uploaded_files
    )
    is_drill_mode = body.get("drill_mode", False) or has_image
    drill_state: DrillState | None = None

    # 检查是否是继续执行演练的确认消息
    CONFIRM_MSGS = {"开始", "继续", "确认", "开始执行", "继续执行"}
    is_confirm_msg = message.strip() in CONFIRM_MSGS

    # 1. 确定会话 ID
    if session_id:
        sid = int(session_id)
        history = _get_history(sid)
        # 检查会话是否已经是演练模式
        session_is_drill = AiModel.get_session_drill_mode(sid)
        if session_is_drill:
            is_drill_mode = True
        # 如果是已有会话进入了演练模式，更新会话标记
        if is_drill_mode:
            AiModel.update_session_drill_mode(sid, 1)
    else:
        # 创建新会话
        title = message[:20] + "..." if len(message) > 20 else message
        sid = AiModel.create_session(
            title=title,
            context_type=context_type,
            context_id=context_id,
            is_drill_mode=1 if is_drill_mode else 0,
        )
        history = []

        # 注入初始上下文
        sys_info = _get_system_context()
        if context_type and context_id:
            sys_info += f"\n当前焦点上下文: {context_type} = {context_id}"
            if context_type == "host":
                from database.models import NmapModel

                host = NmapModel.get_host_by_ip(context_id)
                if host:
                    sys_info += (
                        f"\n详细资产数据: {json.dumps(host, ensure_ascii=False)}"
                    )

        history.append(
            {
                "role": "system",
                "content": f"你叫玄枢指挥官，你是一个专业的网络安全助手。背景：\n{sys_info}",
                "ts": _now_iso(),
            }
        )
        with _session_lock:
            _chat_sessions[sid] = history

    # 初始化演练状态（如果是演练模式）
    if is_drill_mode and not is_confirm_msg:
        drill_state = DrillState()
        drill_state.document_content = message
        unified_log("AIChat", f"进入演练模式 | doc_len={len(message)}", "INFO")
    elif is_drill_mode and is_confirm_msg and history:
        # 从历史中重建演练状态
        drill_state = DrillState()
        for msg in reversed(history):
            if msg.get("role") == "user" and len(str(msg.get("content", ""))) > 50:
                drill_state.document_content = msg.get("content", "")
                break
        unified_log("AIChat", f"继续演练模式 | 确认消息={message}", "INFO")

    # 2. 保存并追加用户消息
    history.append(
        {
            "role": "user",
            "content": message,
            "openai_content": openai_content,
            "ts": _now_iso(),
        }
    )
    AiModel.save_message(sid, "user", message, openai_content=openai_content)

    def generate():
        nonlocal drill_state
        # 如果是新会话，流开始的第一帧直接告诉前端建立的会话 ID
        if not session_id:
            yield f"data: {json.dumps({'session_id': sid}, ensure_ascii=False)}\n\n"

        # ── 演练模式 ────────────────────────────────────────────────────────────
        if is_drill_mode and drill_state:
            # 发送演练启动消息
            if is_confirm_msg:
                yield f"data: {json.dumps({'content': '🚀 继续执行演练...'}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'content': '🚀 演练启动：AI 正在分析演练文档，制定行动计划...'}, ensure_ascii=False)}\n\n"

            # 获取会话历史（用于继续执行）
            session_history = AiModel.get_messages(sid) if is_confirm_msg else None

            # 演练执行器会发送 step_complete 事件，每步完成后保存到数据库
            for chunk in create_drill_stream(
                document_content=drill_state.document_content,
                cfg=cfg_now,
                state=drill_state,
                session_history=session_history,
                openai_content=openai_content,
            ):
                import logging

                try:
                    parsed_chunk = json.loads(chunk.strip())
                    chunk_type = (
                        "tool_result"
                        if "tool_result" in parsed_chunk
                        else (
                            "tool_call"
                            if "tool_call" in parsed_chunk
                            else (
                                "content"
                                if "content" in parsed_chunk
                                else (
                                    "step_complete"
                                    if "step_complete" in parsed_chunk
                                    else "other"
                                )
                            )
                        )
                    )
                    logging.info(f"[DrillSSE] {chunk_type}: {str(parsed_chunk)[:200]}")
                    # step_complete 事件包含完整的 assistant message，保存到数据库
                    if parsed_chunk.get("step_complete"):
                        step_data = parsed_chunk["step_complete"]
                        AiModel.save_message(
                            sid,
                            "assistant",
                            step_data.get("content") or "",
                            tool_calls=step_data.get("tool_calls"),
                        )
                    # tool_result 事件也需要保存为 role='tool'，这样 get_reports 才能找到报告
                    if parsed_chunk.get("tool_result"):
                        tr = parsed_chunk["tool_result"]
                        # 如果是报告生成工具，保存完整的报告内容（get_reports 查找 role='tool' 且 content 包含 "report": 的记录）
                        if tr.get("name") == "generate_report" and tr.get(
                            "full_result"
                        ):
                            try:
                                full_result = json.loads(tr["full_result"])
                                AiModel.save_message(
                                    sid,
                                    "tool",
                                    tr["full_result"],
                                    tool_call_id=tr.get("id"),
                                )
                            except:
                                AiModel.save_message(
                                    sid,
                                    "tool",
                                    tr.get("result", ""),
                                    tool_call_id=tr.get("id"),
                                )
                except:
                    logging.info(f"[DrillSSE] raw: {chunk[:100]}")
                yield f"data: {chunk.rstrip()}\n\n"

            yield f"data: {json.dumps({'done': True, 'session_id': sid}, ensure_ascii=False)}\n\n"
            return

        # ── 普通对话模式 ────────────────────────────────────────────────────────
        full_reply = []
        tool_calls_received = []
        # 普通对话只使用普通工具，演练工具在演练模式单独处理
        all_tools_normal = AI_TOOLS

        # 第一轮：LLM 判断内容或调用工具
        for chunk, error, tool_call in stream_openai_chat_with_tools(
            build_openai_messages(history), cfg_now, tools=all_tools_normal
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
            history.append(
                {"role": "assistant", "content": res_content, "ts": _now_iso()}
            )
            AiModel.save_message(sid, "assistant", res_content)
            yield f"data: {json.dumps({'done': True, 'session_id': sid}, ensure_ascii=False)}\n\n"
            return

        # 检查是否需要进入演练模式（AI 智能调用了 drill 工具 或 用户上传了演练文档）
        has_drill_tools = any(
            tc["name"].startswith("drill_") for tc in tool_calls_received
        )
        if has_drill_tools or is_drill_mode:
            # 确保 drill_state 已初始化（is_drill_mode=False 但 AI 首次调用 drill 工具时走此分支）
            if not drill_state:
                drill_state = DrillState()
            if drill_state.document_content == "":
                drill_state.document_content = message
            # 使用独立的演练执行器（create_drill_stream 返回的 chunk 末尾已有 \n\n，需剥除后加 data: 前缀）
            for chunk in create_drill_stream(
                document_content=drill_state.document_content,
                cfg=cfg_now,
                state=drill_state,
            ):
                import logging

                try:
                    parsed_chunk = json.loads(chunk.strip())
                    chunk_type = (
                        "tool_result"
                        if "tool_result" in parsed_chunk
                        else (
                            "tool_call"
                            if "tool_call" in parsed_chunk
                            else (
                                "content"
                                if "content" in parsed_chunk
                                else (
                                    "step_complete"
                                    if "step_complete" in parsed_chunk
                                    else "other"
                                )
                            )
                        )
                    )
                    logging.info(f"[DrillSSE] {chunk_type}: {str(parsed_chunk)[:200]}")
                    # step_complete 事件包含完整的 assistant message，保存到数据库
                    if parsed_chunk.get("step_complete"):
                        step_data = parsed_chunk["step_complete"]
                        AiModel.save_message(
                            sid,
                            "assistant",
                            step_data.get("content") or "",
                            tool_calls=step_data.get("tool_calls"),
                        )
                    # tool_result 事件也需要保存为 role='tool'，这样 get_reports 才能找到报告
                    if parsed_chunk.get("tool_result"):
                        tr = parsed_chunk["tool_result"]
                        # 如果是报告生成工具，保存完整的报告内容（get_reports 查找 role='tool' 且 content 包含 "report": 的记录）
                        if tr.get("name") == "generate_report" and tr.get(
                            "full_result"
                        ):
                            try:
                                full_result = json.loads(tr["full_result"])
                                AiModel.save_message(
                                    sid,
                                    "tool",
                                    tr["full_result"],
                                    tool_call_id=tr.get("id"),
                                )
                            except:
                                AiModel.save_message(
                                    sid,
                                    "tool",
                                    tr.get("result", ""),
                                    tool_call_id=tr.get("id"),
                                )
                except:
                    logging.info(f"[DrillSSE] raw: {chunk[:100]}")
                yield f"data: {chunk.rstrip()}\n\n"

            yield f"data: {json.dumps({'done': True, 'session_id': sid}, ensure_ascii=False)}\n\n"
            return

        # 执行普通工具并处理（支持多轮循环）
        for chunk in _run_agent_loop(history, all_tools_normal, cfg_now, sid):
            yield f"data: {chunk}\n\n"
        yield f"data: {json.dumps({'done': True, 'session_id': sid}, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
            "Content-Encoding": "identity",
            "Connection": "keep-alive",
        },
    )


def _run_agent_loop(history: list, tools: list, cfg: dict, sid: int):
    """
    普通模式 Agent 循环（生成器）。每次 yield 返回完整的 SSE data 行。
    LLM决定工具 → 执行 → 结果给LLM → 继续直到完成
    """
    max_steps = 30
    step_count = 0

    def _execute_tool(tool_name: str, arguments: dict) -> str:
        """统一工具执行入口 - 仅处理系统工具"""
        return execute_tool(tool_name, arguments, cfg)

    # ─── Agent 主循环 ──────────────────────────────────────────────────────
    while step_count < max_steps:
        step_count += 1

        # 发送步骤开始
        yield json.dumps(
            {
                "drill_step": {
                    "step": step_count,
                    "status": "thinking",
                    "message": f"🤔 AI 正在思考下一步... (第 {step_count}/{max_steps} 步)",
                }
            }
        )

        tool_calls = []
        text_chunks = []

        # LLM 决策
        for chunk, error, tool_call in stream_openai_chat_with_tools(
            build_openai_messages(history), cfg, tools=tools
        ):
            if error:
                yield json.dumps({"error": error})
                return
            if chunk:
                text_chunks.append(chunk)
                yield json.dumps({"content": chunk})
            if tool_call:
                tool_calls.append(tool_call)

        response_text = "".join(text_chunks)
        if response_text and not tool_calls:
            # 无工具调用时才保存纯文本回复，避免与带 tool_calls 的消息重复
            history.append({"role": "assistant", "content": response_text})

        # 无工具调用则结束
        if not tool_calls:
            unified_log(
                "AIChat", f"Agent循环结束（无更多工具调用）| 共 {step_count} 步", "INFO"
            )
            break

        # 保存 assistant tool_call 消息
        history.append(
            {
                "role": "assistant",
                "content": response_text or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(
                                tc["arguments"], ensure_ascii=False
                            ),
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        # 持久化 assistant tool_call 消息，避免前端断开后工具链记录丢失
        try:
            AiModel.save_message(
                sid,
                "assistant",
                response_text or "",
                tool_calls=[
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(
                                tc["arguments"], ensure_ascii=False
                            ),
                        },
                    }
                    for tc in tool_calls
                ],
            )
        except Exception:
            pass

        # ─── 执行工具 ────────────────────────────────────────────────────────
        for tc in tool_calls:
            tool_name = tc["name"]
            tool_args = tc["arguments"]

            # 发送工具调用开始
            yield json.dumps(
                {
                    "tool_call": {
                        "id": tc["id"],
                        "name": tool_name,
                        "arguments": tool_args,
                        "status": "executing",
                    }
                }
            )

            # 执行工具
            res = _execute_tool(tool_name, tool_args)

            # 发送给前端（截断过长结果）
            display = res[:800] + "..." if len(res) > 800 else res

            yield json.dumps(
                {
                    "tool_result": {
                        "id": tc["id"],
                        "tool_call_id": tc["id"],  # 前端匹配所需
                        "name": tool_name,
                        "result": display,
                        "full_result": res,
                        "status": "done",
                    }
                }
            )

            # 保存工具结果
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": res,
                    "ts": _now_iso(),
                }
            )
            # 持久化 tool 结果，支持切页后历史恢复
            try:
                AiModel.save_message(
                    sid,
                    "tool",
                    res,
                    tool_call_id=tc["id"],
                )
            except Exception:
                pass

    # 保存最后一条 assistant 消息
    if history and history[-1].get("role") == "assistant":
        try:
            AiModel.save_message(sid, "assistant", history[-1].get("content") or "")
        except Exception:
            pass


def _build_report_prompt(
    state: DrillState,
    hfish: dict,
    scan_data: list,
    bruteforce_data: list,
    honeypot_data: list,
    ban_data: list,
    findings_data: list,
    screenshots_data: list,
) -> str:
    """构造 AI 报告生成 Prompt，包含所有演练数据"""
    from datetime import datetime

    elapsed = (datetime.now() - state._start_time).total_seconds()
    elapsed_str = (
        f"{int(elapsed) // 60}分{int(elapsed) % 60}秒"
        if elapsed >= 60
        else f"{int(elapsed)}秒"
    )

    # 蜜罐统计
    service_stats = hfish.get("service_stats", [])
    ip_stats = hfish.get("ip_stats", [])
    time_stats = hfish.get("time_stats", [])
    hfish_total = hfish.get("total", 0)

    # 扫描汇总
    total_hosts = sum(r.get("result", {}).get("发现主机", 0) for r in scan_data)
    scan_targets = [r.get("target", "") for r in scan_data if r.get("target")]

    # 弱口令
    vulnerable_bf = [
        r for r in bruteforce_data if r.get("result", {}).get("vulnerable")
    ]

    # 格式化 JSON 数据供 AI 分析
    import json

    context = {
        "演练开始时间": state._start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "运行时长": elapsed_str,
        "目标网络": state.target_network or "未指定",
        "执行步骤": state.step_count,
        "扫描结果": scan_data,
        "弱口令检测结果": bruteforce_data,
        "蜜罐审计结果": honeypot_data,
        "封禁记录": ban_data,
        "发现的问题": findings_data,
        "截图记录": screenshots_data,
        "蜜罐总攻击次数": hfish_total,
        "蜜罐服务统计": service_stats,
        "蜜罐攻击来源Top10": ip_stats,
        "蜜罐7天趋势": time_stats,
        "网络扫描次数": len(scan_data),
        "发现主机数": total_hosts,
        "弱口令风险数": len(vulnerable_bf),
        "蜜罐审计次数": len(honeypot_data),
        "封禁IP数": len(ban_data),
        "安全问题数": len(findings_data),
    }
    ctx_json = json.dumps(context, ensure_ascii=False, indent=2)

    prompt = f"""你是「玄枢指挥官」，一个专业的网络安全 AI。请根据以下演练数据生成一份**完整的 HTML 安全演练报告**。

## 核心要求
1. 输出**完整的单个 HTML 页面**（包含 <!DOCTYPE html> 和 <html>），不要只输出片段
2. 使用 **ECharts**（CDN: https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js）绘制图表
3. 使用 **Bootstrap 5**（CDN）美化布局，响应式设计
4. **暗黑军事风格**：深色背景(#0a0e14 或 #1a1a2e)，亮色文字(#00ff88, #ff6b6b, #ffd93d)，科技感字体
5. 所有中文内容，图表标题和标签也必须是中文

## 必须包含的板块（全部都要有，缺一不可）

### 1. 报告头部
- 标题：「🛡️ 安全演练报告」
- 副标题：演练时间、目标网络、运行时长
- 状态标签：总体风险等级（根据发现数量动态评定）

### 2. 执行摘要卡片
- 4~6 个 KPI 卡片横向排列：扫描主机数、弱口令风险数、蜜罐攻击次数、封禁IP数、安全问题数、审计时长
- 每个卡片带图标和颜色区分

### 3. ECharts 图表区（至少 3 个图表）
**图表1 - 7天攻击趋势（折线图）**
- 数据：{json.dumps(time_stats, ensure_ascii=False)}
- X轴：日期，Y轴：攻击次数
- 线条颜色：渐变绿 (#00ff88)

**图表2 - 攻击服务分布（饼图）**
- 数据：{json.dumps(service_stats, ensure_ascii=False)}
- 饼图，带标签显示服务名和次数

**图表3 - Top 10 攻击来源（水平柱状图）**
- 数据：{json.dumps(ip_stats[:10], ensure_ascii=False)}
- IP地址为Y轴，攻击次数为X轴
- 颜色：橙色渐变

### 4. 网络扫描详情
- 扫描目标：{", ".join(scan_targets) or "无"}
- 发现主机：{total_hosts} 台
- 若有主机数据，列出 IP、端口、服务

### 5. 弱口令检测结果
- 共检测 {len(bruteforce_data)} 个服务
- 若有发现，**红色高亮**显示每个弱口令（用户名/密码）
- 若无发现，显示「未发现常见弱口令」

### 6. 蜜罐审计记录
- 最新攻击记录表格（时间、来源IP、服务类型）
- 从 honeypot_data 中提取，若无则从 service_stats 描述

### 7. 封禁IP列表
- 列出所有已封禁IP和原因
- 若无，显示「暂无封禁记录」

### 8. 安全问题汇总表
- 按 severity 分组（严重/高危/中危/信息）
- 包含：类型、IP地址、端口、描述

### 9. 修复建议
- 按优先级列出具体修复步骤
- 每个建议对应一个问题

### 10. 页脚
- 「本报告由玄枢·AI 攻防指挥官自动生成 | 生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}」

## 完整演练数据（JSON）
```json
{ctx_json}
```

请立即生成完整 HTML，不要解释，直接输出 HTML 代码。
"""
    return prompt


def _generate_drill_report(state: DrillState) -> str:
    """生成演练 Markdown 报告"""
    from datetime import datetime

    # 单次遍历，按 severity 分组
    grouped = {"critical": [], "high": [], "medium": [], "info": []}
    for f in state.findings:
        grouped.get(f.get("severity", "info"), grouped["info"]).append(f)
    critical, high, medium, info = (
        grouped["critical"],
        grouped["high"],
        grouped["medium"],
        grouped["info"],
    )

    report = f"""# 🛡️ 安全演练报告

> **生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
> **目标网络**: {state.target_network or "未指定"}

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

共执行 **{len(state.scan_results)}** 次网络扫描，发现 **{sum(r.get("result", {}).get("发现主机", 0) for r in state.scan_results)}** 台主机

"""

    for sr in state.scan_results:
        r = sr.get("result", {})
        hosts = r.get("主机列表", [])
        if hosts:
            report += (
                f"**目标 {sr.get('target', 'N/A')}** — {r.get('发现主机', 0)} 台主机\n"
            )
            for h in hosts[:10]:
                report += f"- `{h.get('ip', 'N/A')}` : {h.get('ports', 'N/A')}\n"

    if state.screenshot_results:
        report += f"""
---

## Web 截图

共采集 **{len(state.screenshot_results)}** 张截图

| IP | 端口 | URL | 截图 |
|----|------|-----|------|
"""
        for sr in state.screenshot_results:
            screenshot_url = sr.get("screenshot_url", "")
            if screenshot_url:
                report += f"| `{sr.get('ip', 'N/A')}` | {sr.get('port', 'N/A')} | {sr.get('url', 'N/A')} | ![截图]({screenshot_url}) |\n"
            else:
                report += f"| `{sr.get('ip', 'N/A')}` | {sr.get('port', 'N/A')} | {sr.get('url', 'N/A')} | 无 |\n"

    vulnerable_bf = [
        r for r in state.bruteforce_results if r.get("result", {}).get("vulnerable")
    ]
    if vulnerable_bf:
        report += f"""
---

## 🔴 弱口令检测 — 发现 {len(vulnerable_bf)} 个风险！

"""
        for r in vulnerable_bf:
            result = r.get("result", {})
            for cred in result.get("vulnerable_creds", []):
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
