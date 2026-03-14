"""
AI Module - AI Chat and analysis endpoints
"""
import threading
from flask import Blueprint, request, g
from ai_runtime import (
    build_openai_messages,
    call_openai_chat_completion,
    execute_tool_calls,
    get_tool_definitions,
)
from database.models import AiModel
from .helpers import (
    require_auth, ok, err, _body, _load_cfg, _save_cfg,
    _now_iso, _read_chat_system_prompt
)
from utils.logger import log as unified_log

ai_bp = Blueprint('ai', __name__)

# Chat sessions (in-memory)
_chat_sessions: dict[int, list] = {}
_session_counter = 0
_session_lock = threading.Lock()


def _next_session_id():
    """线程安全地分配会话 ID"""
    global _session_counter
    with _session_lock:
        _session_counter += 1
        return _session_counter


def _call_ai(messages: list, cfg: dict, tools: list | None = None) -> dict:
    """调用 OpenAI-compatible 接口，返回 {content, tool_calls}"""
    return call_openai_chat_completion(messages, cfg, tools=tools)


def _serialize_tool_call(tool_call: dict) -> dict:
    return {
        'id': tool_call.get('id', ''),
        'type': tool_call.get('type', 'function'),
        'name': tool_call.get('name', ''),
        'arguments': tool_call.get('arguments', {}),
    }


def _serialize_chat_message(message: dict) -> dict:
    payload = {
        'role': message.get('role', ''),
        'content': message.get('content') or '',
        'created_at': message.get('ts', _now_iso()),
    }
    if message.get('role') == 'assistant' and message.get('tool_calls'):
        payload['tool_calls'] = [_serialize_tool_call(item) for item in (message.get('tool_calls') or [])]
    if message.get('role') == 'tool':
        payload['tool_call_id'] = message.get('tool_call_id', '')
        payload['name'] = message.get('name', '')
    return payload


def _run_ai_tool_rounds(history: list[dict], cfg: dict, tool_defs: list[dict]) -> tuple[str, list[dict]]:
    generated_messages: list[dict] = []
    reply = ''

    for _ in range(5):
        result = _call_ai(build_openai_messages(history), cfg, tools=tool_defs)
        content = result.get('content', '')
        tool_calls = result.get('tool_calls', [])

        assistant_message = {'role': 'assistant', 'content': content, 'ts': _now_iso()}
        if tool_calls:
            assistant_message['tool_calls'] = tool_calls
        history.append(assistant_message)
        generated_messages.append(assistant_message)

        if not tool_calls:
            reply = content
            break

        tool_messages = execute_tool_calls(tool_calls)
        for item in tool_messages:
            item['ts'] = _now_iso()
            history.append(item)
            generated_messages.append(item)
    else:
        reply = '⚠️ 工具调用轮次已达上限，请缩小问题范围后重试。'
        fallback_message = {'role': 'assistant', 'content': reply, 'ts': _now_iso()}
        history.append(fallback_message)
        generated_messages.append(fallback_message)

    return reply, generated_messages


@ai_bp.route('/sessions', methods=['GET'])
@require_auth
def ai_sessions():
    """Get AI sessions"""
    sessions = [{'id': sid, 'title': f'对话 #{sid}',
                 'context_type': None, 'context_id': None,
                 'operator': g.user.get('username', ''),
                 'created_at': _chat_sessions.get(sid, [{}])[-1].get('ts', _now_iso()) if _chat_sessions.get(sid) else _now_iso(),
                 'started_at': _now_iso(),
                 'expires_at': None}
                for sid in _chat_sessions.keys()]
    return ok(sessions)


@ai_bp.route('/sessions/<int:session_id>/messages', methods=['GET'])
@require_auth
def ai_session_messages(session_id: int):
    """Get session messages"""
    msgs = _chat_sessions.get(session_id, [])
    out = []
    for m in msgs:
        role = m.get('role')
        if role == 'system':
            continue
        if role in ('user', 'assistant', 'tool'):
            out.append(_serialize_chat_message(m))
    return ok(out)


@ai_bp.route('/sessions/<int:session_id>', methods=['DELETE'])
@require_auth
def ai_session_delete(session_id: int):
    """Delete session"""
    _chat_sessions.pop(session_id, None)
    return ok()


@ai_bp.route('/chat', methods=['POST'])
@require_auth
def ai_chat():
    """AI Chat endpoint"""
    unified_log('AIChat', f'收到 /api/v1/ai/chat 请求 from={request.remote_addr}', 'INFO')

    body = _body()
    message = body.get('message', '').strip()
    session_id = body.get('session_id')

    if not message:
        return err('消息不能为空')

    cfg_load = _load_cfg()
    sys_prompt, migrated = _read_chat_system_prompt(cfg_load)
    if migrated:
        _save_cfg(cfg_load)

    if session_id and session_id in _chat_sessions:
        sid = session_id
        history = _chat_sessions[sid]
    else:
        sid = _next_session_id()
        history = [{'role': 'system', 'content': sys_prompt}] if sys_prompt else []
        _chat_sessions[sid] = history

    ts = _now_iso()
    history.append({'role': 'user', 'content': message, 'ts': ts})
    cfg_now = _load_cfg()

    # Tool definitions
    _TOOL_DEFS = get_tool_definitions()

    # First call with tools
    reply, turn_messages = _run_ai_tool_rounds(history, cfg_now, _TOOL_DEFS)

    # Save to DB
    try:
        AiModel.save_chat_history(message, reply)
    except Exception:
        pass

    return ok({
        'session_id': sid,
        'reply': reply,
        'messages': [_serialize_chat_message(item) for item in turn_messages],
        'context': {'type': None, 'id': None},
    })
