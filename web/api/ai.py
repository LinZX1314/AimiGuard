"""
AI Module - AI Chat endpoints
"""
import json
import threading
from flask import Blueprint, request, g, Response, stream_with_context
from ai import (
    build_openai_messages,
    call_openai_chat_completion,
    stream_openai_chat_completion,
)
from database.models import AiModel
from .helpers import (
    require_auth, ok, err, _body, _load_cfg, _save_cfg,
    _now_iso
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


def _call_ai(messages: list, cfg: dict) -> dict:
    """调用 OpenAI-compatible 接口，返回 {content}"""
    return call_openai_chat_completion(messages, cfg)


def _serialize_chat_message(message: dict) -> dict:
    payload = {
        'role': message.get('role', ''),
        'content': message.get('content') or '',
        'created_at': message.get('ts', _now_iso()),
    }
    return payload


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
        if role in ('user', 'assistant'):
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

    if session_id and session_id in _chat_sessions:
        sid = session_id
        history = _chat_sessions[sid]
    else:
        sid = _next_session_id()
        history = []
        _chat_sessions[sid] = history

    ts = _now_iso()
    history.append({'role': 'user', 'content': message, 'ts': ts})
    cfg_now = _load_cfg()

    # 调用 AI（无工具）
    result = _call_ai(build_openai_messages(history), cfg_now)
    reply = result.get('content', '')

    assistant_message = {'role': 'assistant', 'content': reply, 'ts': _now_iso()}
    history.append(assistant_message)

    # Save to DB
    try:
        AiModel.save_chat_history(message, reply)
    except Exception:
        pass

    return ok()


@ai_bp.route('/chat/stream', methods=['POST'])
@require_auth
def ai_chat_stream():
    """AI Chat streaming endpoint"""
    unified_log('AIChat', f'收到 /api/v1/ai/chat/stream 请求 from={request.remote_addr}', 'INFO')

    body = _body()
    message = body.get('message', '').strip()
    session_id = body.get('session_id')

    if not message:
        return err('消息不能为空')

    if session_id and session_id in _chat_sessions:
        sid = session_id
        history = _chat_sessions[sid]
    else:
        sid = _next_session_id()
        history = []
        _chat_sessions[sid] = history

    ts = _now_iso()
    history.append({'role': 'user', 'content': message, 'ts': ts})
    cfg_now = _load_cfg()

    full_reply = []

    def generate():
        import time
        nonlocal full_reply
        full_reply = []

        for chunk, error in stream_openai_chat_completion(
            build_openai_messages(history),
            cfg_now
        ):
            if error:
                yield f"data: {json.dumps({'error': error})}\n\n"
                return
            if chunk:
                full_reply.append(chunk)
                data = f"data: {json.dumps({'content': chunk})}\n\n"
                yield data

        # 保存到历史
        reply_text = ''.join(full_reply)
        assistant_message = {'role': 'assistant', 'content': reply_text, 'ts': _now_iso()}
        history.append(assistant_message)

        # 保存到数据库
        try:
            AiModel.save_chat_history(message, reply_text)
        except Exception:
            pass

        yield f"data: {json.dumps({'done': True, 'session_id': sid})}\n\n"

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
    """Clear current session"""
    _chat_sessions.clear()
