"""
AI Module - AI Chat and analysis endpoints
"""
import json
import threading
from datetime import datetime
from flask import Blueprint, request, g
from database.models import AiModel
from .helpers import (
    require_auth, ok, err, _body, _load_cfg, _save_cfg,
    _now_iso, _read_chat_system_prompt
)
from utils.logger import log as unified_log

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')

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


def _ai_diag(cfg: dict, message: str, level: str = 'INFO'):
    """统一 AI 诊断日志输出"""
    try:
        enabled = cfg.get('logging', {}).get('ai_log', True)
    except Exception:
        enabled = True
    if enabled:
        unified_log('AIChat', message, level)


def _call_ai(messages: list, cfg: dict, tools: list | None = None) -> dict:
    """调用 OpenAI-compatible 接口，返回 {content, tool_calls}"""
    import urllib.error
    import urllib.request
    from json import JSONDecodeError

    def _candidate_chat_urls(raw_url: str) -> list[str]:
        u = (raw_url or '').strip().rstrip('/')
        if not u:
            return []
        low = u.lower()
        cands: list[str] = []

        if low.endswith('/chat/completions'):
            cands.append(u)
        elif low.endswith('/v1'):
            cands.append(f'{u}/chat/completions')
            cands.append(f'{u[:-3]}/chat/completions')
        else:
            cands.append(f'{u}/v1/chat/completions')
            cands.append(f'{u}/chat/completions')

        seen = set()
        ordered = []
        for item in cands:
            if item and item not in seen:
                ordered.append(item)
                seen.add(item)
        return ordered

    ai_cfg = cfg.get('ai', {})
    api_url = ai_cfg.get('api_url', '')
    api_key = ai_cfg.get('api_key', '')
    model = ai_cfg.get('model', 'gpt-3.5-turbo')
    timeout = int(ai_cfg.get('timeout', 60))
    endpoints = _candidate_chat_urls(api_url)

    if not endpoints:
        return {'content': '⚠️ AI 接口未配置，请在设置中填写 api_url。', 'tool_calls': []}

    req_body: dict = {'model': model, 'messages': messages, 'stream': False}
    if tools:
        req_body['tools'] = tools
        req_body['tool_choice'] = 'auto'
    body = json.dumps(req_body).encode()
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    last_http_error = None
    last_parse_error = None
    for endpoint in endpoints:
        req = urllib.request.Request(endpoint, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status_code = getattr(resp, 'status', None) or getattr(resp, 'code', None)
                raw_bytes = resp.read()
                raw_text = raw_bytes.decode('utf-8', errors='ignore').strip()

                if not raw_text:
                    last_parse_error = f'空响应 @ {endpoint}'
                    continue

                try:
                    data = json.loads(raw_text)
                except JSONDecodeError:
                    snippet = raw_text[:200].replace('\n', ' ')
                    last_parse_error = f'非 JSON 响应 @ {endpoint}: {snippet}'
                    continue

                try:
                    msg = data['choices'][0]['message']
                    content = msg.get('content') or ''
                    raw_tcs = msg.get('tool_calls') or []
                    parsed_tcs = []
                    for tc in raw_tcs:
                        try:
                            args = json.loads(tc['function']['arguments'])
                        except Exception:
                            args = {}
                        parsed_tcs.append({
                            'id': tc.get('id', ''),
                            'name': tc['function']['name'],
                            'arguments': args,
                        })
                    return {'content': content, 'tool_calls': parsed_tcs}
                except Exception:
                    preview = json.dumps(data, ensure_ascii=False)[:300]
                    last_parse_error = f'JSON 结构非 OpenAI 格式 @ {endpoint}: {preview}'
                    continue
        except urllib.error.HTTPError as e:
            detail = ''
            try:
                detail = e.read().decode('utf-8', errors='ignore')
            except Exception:
                pass
            if e.code == 404:
                last_http_error = f'HTTP 404 Not Found @ {endpoint}'
                continue
            if detail:
                return {'content': f'⚠️ AI 调用失败: HTTP {e.code} {e.reason} - {detail[:300]}', 'tool_calls': []}
            return {'content': f'⚠️ AI 调用失败: HTTP {e.code} {e.reason}', 'tool_calls': []}
        except Exception as e:
            return {'content': f'⚠️ AI 调用失败: {e}', 'tool_calls': []}

    if last_http_error:
        return {'content': f'⚠️ AI 调用失败: {last_http_error}', 'tool_calls': []}
    if last_parse_error:
        return {'content': f'⚠️ AI 调用失败: {last_parse_error}', 'tool_calls': []}
    return {'content': '⚠️ AI 调用失败: 未知错误。', 'tool_calls': []}


@ai_bp.route('/sessions', methods=['GET'])
@require_auth
def ai_sessions():
    """Get AI sessions"""
    sessions = [{'id': sid, 'title': f'对话 #{sid}',
                 'context_type': None, 'context_id': None,
                 'operator': g.user.get('username', ''),
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
        if role == 'tool':
            continue
        content = m.get('content') or ''
        if role == 'assistant' and not content and m.get('tool_calls'):
            content = '🔧 已执行工具调用'
        if role in ('user', 'assistant'):
            out.append({'role': role, 'content': content, 'created_at': m.get('ts', _now_iso())})
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
    _TOOL_DEFS = [
        {
            'type': 'function',
            'function': {
                'name': 'nmap_scan',
                'description': '执行 Nmap 网络扫描，返回主机与端口信息',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'target': {'type': 'string', 'description': '目标 IP、域名或网段'},
                        'arguments': {'type': 'string', 'description': 'nmap 参数'}
                    },
                    'required': ['target']
                }
            }
        }
    ]

    def _exec_nmap_scan(args: dict) -> str:
        """执行 nmap 扫描并写库"""
        try:
            from plugin.network_scan import scan_hosts, parse_scan_results
            from database.models import ScannerModel

            target = (args.get('target') or '').strip()
            raw_args = args.get('arguments', '-sV -O -T4')
            nmap_args = str(raw_args) if raw_args else '-sV -O -T4'
            if not target:
                return json.dumps({'error': '缺少 target 参数'}, ensure_ascii=False)

            nm = scan_hosts(target, nmap_args)
            if not nm:
                return json.dumps({'error': 'Nmap 执行失败'}, ensure_ascii=False)

            hosts = parse_scan_results(nm)
            try:
                scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                scan_id = ScannerModel.create_scan([target], nmap_args, scan_time)
                count = 0
                for host in hosts:
                    try:
                        open_ports_str = ','.join(map(str, host.get('open_ports', []) or []))
                        services_list = []
                        for svc in host.get('services', []) or []:
                            svc_str = f"{svc.get('port', '')}/{svc.get('service', '')}"
                            if svc.get('product'):
                                svc_str += f" {svc['product']}"
                            if svc.get('version'):
                                svc_str += f" {svc['version']}"
                            services_list.append(svc_str)
                        services_str = '; '.join(services_list)
                        ScannerModel.save_host(scan_id, host, scan_time, open_ports_str, services_str)
                        ScannerModel.upsert_asset(scan_id, host, scan_time)
                        count += 1
                    except Exception:
                        pass
                if count > 0:
                    ScannerModel.increment_hosts_count(scan_id, count)
            except Exception as db_e:
                unified_log('AIChat', f'nmap 结果写库失败: {db_e}', 'WARN')
            return json.dumps(hosts[:15], ensure_ascii=False)
        except Exception as e:
            return json.dumps({'error': str(e)}, ensure_ascii=False)

    _TOOL_HANDLERS = {
        'nmap_scan': _exec_nmap_scan,
    }

    # First call with tools
    msgs_for_ai = [{'role': m['role'], 'content': m.get('content') or ''}
                   for m in history
                   if m['role'] in ('system', 'user', 'assistant')]
    result = _call_ai(msgs_for_ai, cfg_now, tools=_TOOL_DEFS)
    content = result.get('content', '')
    tool_calls = result.get('tool_calls', [])

    if tool_calls:
        history.append({'role': 'assistant', 'content': content, 'tool_calls': tool_calls, 'ts': _now_iso()})
        for tc in tool_calls:
            func_name = tc.get('name', '')
            handler = _TOOL_HANDLERS.get(func_name)
            if handler:
                tool_result = handler(tc.get('arguments', {}))
            else:
                tool_result = json.dumps({'error': f'未知工具: {func_name}'}, ensure_ascii=False)
            history.append({'role': 'tool', 'tool_call_id': tc.get('id', ''), 'name': func_name, 'content': tool_result, 'ts': _now_iso()})

        # Second call
        msgs_for_ai2 = []
        for m in history:
            if m['role'] == 'tool':
                msgs_for_ai2.append({'role': 'tool', 'tool_call_id': m.get('tool_call_id', ''), 'name': m.get('name', ''), 'content': m.get('content', '')})
            elif m['role'] == 'assistant' and m.get('tool_calls'):
                msgs_for_ai2.append({'role': 'assistant', 'content': m.get('content') or '', 'tool_calls': [{'id': t['id'], 'type': 'function', 'function': {'name': t['name'], 'arguments': json.dumps(t['arguments'], ensure_ascii=False)}} for t in m['tool_calls']]})
            else:
                msgs_for_ai2.append({'role': m['role'], 'content': m.get('content') or ''})
        result2 = _call_ai(msgs_for_ai2, cfg_now)
        reply = result2.get('content', '')
        history.append({'role': 'assistant', 'content': reply, 'ts': _now_iso()})
    else:
        reply = content
        history.append({'role': 'assistant', 'content': reply, 'ts': _now_iso()})

    # Save to DB
    try:
        AiModel.save_chat_history(message, reply)
    except Exception:
        pass

    return ok({'session_id': sid, 'reply': reply, 'context': {'type': None, 'id': None}})
