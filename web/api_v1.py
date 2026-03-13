"""
AimiGuard  /api/v1/  REST Blueprint
Compatible with the Vue 3 SPA front-end.
Uses only stdlib + Flask + the existing database models (no extra packages).
JWT-like token: base64url(header).base64url(payload).HMAC-SHA256(key, header.payload)
"""
from __future__ import annotations
import os, sys, json, hmac, hashlib, base64, time, threading
from datetime import datetime
from functools import wraps
from flask import Blueprint, request, jsonify, g

# ─── path setup ───────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
WEB_DIR  = os.path.dirname(os.path.abspath(__file__))
if WEB_DIR not in sys.path:
    sys.path.insert(0, WEB_DIR)

from database.models import (
    NmapModel, VulnModel, HFishModel, StatsModel, AiModel, ScannerModel
)

CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

def _load_cfg():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def _save_cfg(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ─── Blueprint ────────────────────────────────────────────────────────────────
v1 = Blueprint('v1', __name__, url_prefix='/api/v1')

# ─── Simple JWT (stdlib only) ─────────────────────────────────────────────────
_JWT_SECRET = os.environ.get('AIMIGUARD_SECRET', 'aimiguard-secret-key-2026')
_JWT_TTL    = 86400 * 7  # 7 days

def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

def _b64d(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + '=' * (pad % 4))

def _make_token(payload: dict) -> str:
    hdr = _b64e(json.dumps({'typ': 'JWT', 'alg': 'HS256'}).encode())
    pld = _b64e(json.dumps({**payload, 'exp': int(time.time()) + _JWT_TTL}).encode())
    sig = _b64e(hmac.new(_JWT_SECRET.encode(), f'{hdr}.{pld}'.encode(), hashlib.sha256).digest())
    return f'{hdr}.{pld}.{sig}'

def _decode_token(token: str) -> dict | None:
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        hdr, pld, sig = parts
        expected = _b64e(hmac.new(_JWT_SECRET.encode(), f'{hdr}.{pld}'.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64d(pld))
        if payload.get('exp', 0) < time.time():
            return None
        return payload
    except Exception:
        return None

def require_auth(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        header = request.headers.get('Authorization', '')
        token  = header.removeprefix('Bearer ').strip()
        payload = _decode_token(token)
        if payload is None:
            return jsonify({'code': 401, 'message': '未授权'}), 401
        g.user = payload
        return f(*args, **kwargs)
    return wrapped

def ok(data=None, **extra):
    return jsonify({'code': 0, 'message': 'ok', 'data': data, **extra})

def err(msg, code=400):
    return jsonify({'code': code, 'message': msg}), code

# ─── Auth ─────────────────────────────────────────────────────────────────────
@v1.route('/auth/login', methods=['POST'])
def auth_login():
    body = request.get_json(force=True) or {}
    username = body.get('username', '').strip()
    password = body.get('password', '').strip()

    # Check credentials: config.json > default admin/admin123
    cfg = _load_cfg()
    users = cfg.get('users', [{'username': 'admin', 'password': 'admin123', 'role': 'admin'}])
    matched = next((u for u in users if u['username'] == username and u['password'] == password), None)
    if not matched:
        return err('用户名或密码错误', 401)

    user_info = {
        'username': matched['username'],
        'role':     matched.get('role', 'operator'),
        'permissions': matched.get('permissions', ['*']),
    }
    token = _make_token({'sub': username, **user_info})
    return jsonify({
        'access_token': token,
        'token_type':   'bearer',
        'user':         user_info,
    })

@v1.route('/auth/logout', methods=['POST'])
def auth_logout():
    return ok()

@v1.route('/auth/refresh', methods=['POST'])
@require_auth
def auth_refresh():
    token = _make_token({k: v for k, v in g.user.items() if k != 'exp'})
    return jsonify({'access_token': token, 'token_type': 'bearer'})

@v1.route('/auth/profile', methods=['GET'])
@require_auth
def auth_profile():
    return ok({'username': g.user.get('username'), 'role': g.user.get('role'),
               'permissions': g.user.get('permissions', [])})

# ─── Overview ─────────────────────────────────────────────────────────────────
@v1.route('/overview/metrics', methods=['GET'])
@require_auth
def overview_metrics():
    hfish = HFishModel.get_stats()
    nmap_stats = NmapModel.get_stats()
    vuln  = VulnModel.get_vuln_stats()

    high_count  = next((s['count'] for s in hfish.get('threat_stats', []) if s['level'] in ('高危','HIGH')), 0)
    online      = next((s['count'] for s in nmap_stats.get('state_stats', []) if s['state'] == 'up'), 0)
    ai_analyses = AiModel.get_all_analyses()
    blocked     = sum(1 for a in ai_analyses.values() if a.get('decision') == 'true')

    return ok({
        'hfish_total':  hfish.get('total', 0),
        'hfish_high':   high_count,
        'nmap_online':  online,
        'vuln_open':    vuln.get('vulnerable', 0),
        'ai_decisions': len(ai_analyses),
        'blocked_ips':  blocked,
    })

@v1.route('/overview/chain-status', methods=['GET'])
@require_auth
def overview_chain_status():
    cfg = _load_cfg()
    return ok({
        'hfish_sync':   cfg.get('hfish', {}).get('sync_enabled', False),
        'nmap_scan':    cfg.get('nmap',  {}).get('scan_enabled',  False),
        'ai_analysis':  cfg.get('ai',    {}).get('enabled',       False),
        'acl_auto_ban': cfg.get('ai',    {}).get('auto_ban',      False),
    })

@v1.route('/overview/trends', methods=['GET'])
@require_auth
def overview_trends():
    hfish = HFishModel.get_stats()
    time_stats = hfish.get('time_stats', [])
    return ok({
        'range':            request.args.get('range', '7d'),
        'alert_trend':      [{'date': s['date'], 'count': s['count']} for s in time_stats],
        'high_alert_trend': [],
        'task_trend':       [],
    })

# ─── Defense / HFish ──────────────────────────────────────────────────────────
@v1.route('/defense/hfish/logs', methods=['GET'])
@require_auth
def defense_hfish_logs():
    limit       = int(request.args.get('limit', 200))
    offset      = int(request.args.get('offset', 0))
    aggregated  = request.args.get('aggregated', '0') in ('1', 'true', 'yes')
    service_name= request.args.get('service_name')
    threat_level= request.args.get('threat_level')

    if aggregated:
        from database.db import get_connection
        conn = get_connection()
        c    = conn.cursor()
        q    = """
            SELECT attack_ip, ip_location, service_name,
                   COUNT(*) as attack_count,
                   MAX(create_time_str) as latest_time
            FROM attack_logs WHERE 1=1
        """
        params: list = []
        if service_name:
            q += ' AND service_name = ?'; params.append(service_name)
        q += ' GROUP BY attack_ip ORDER BY attack_count DESC LIMIT ? OFFSET ?'
        params += [limit, offset]
        c.execute(q, params)
        rows = [dict(r) for r in c.fetchall()]
        conn.close()

        ai_all = AiModel.get_all_analyses()
        for row in rows:
            a = ai_all.get(row['attack_ip'])
            row['decision']    = a['decision']      if a else None
            row['ai_analysis'] = a['analysis_text'] if a else None
        return ok({'items': rows, 'total': len(rows)})

    logs = HFishModel.get_attack_logs(limit=limit, offset=offset,
                                      threat_level=threat_level,
                                      service_name=service_name)
    return ok({'items': logs, 'total': len(logs)})

@v1.route('/defense/hfish/stats', methods=['GET'])
@require_auth
def defense_hfish_stats():
    return ok(HFishModel.get_stats())

@v1.route('/defense/hfish/sync', methods=['POST'])
@require_auth
def defense_hfish_sync():
    def _do():
        try:
            cfg = _load_cfg()
            sys.path.insert(0, os.path.join(BASE_DIR, 'hfish'))
            from hfish.attack_log_sync import HFishSyncer
            syncer = HFishSyncer(cfg)
            syncer.run_once()
        except Exception as e:
            pass
    threading.Thread(target=_do, daemon=True).start()
    return ok({'message': '同步任务已触发'})

@v1.route('/defense/hfish/config', methods=['GET'])
@require_auth
def hfish_config_get():
    cfg = _load_cfg()
    h   = cfg.get('hfish', {})
    return ok({
        'host_port':      h.get('host_port'),
        'api_base_url':   h.get('api_base_url'),
        'sync_interval':  h.get('sync_interval', 60),
        'enabled':        h.get('sync_enabled', False),
    })

@v1.route('/defense/hfish/config', methods=['POST'])
@require_auth
def hfish_config_save():
    body = request.get_json(force=True) or {}
    cfg  = _load_cfg()
    h    = cfg.setdefault('hfish', {})
    if 'host_port'     in body: h['host_port']      = body['host_port']
    if 'api_key'       in body: h['api_key']         = body['api_key']
    if 'sync_interval' in body: h['sync_interval']   = int(body['sync_interval'])
    if 'enabled'       in body: h['sync_enabled']    = bool(body['enabled'])
    if 'api_base_url'  in body: h['api_base_url']    = body['api_base_url']
    _save_cfg(cfg)
    return ok()

# ─── Defense events (using attack_logs as proxy) ─────────────────────────────
@v1.route('/defense/events', methods=['GET'])
@require_auth
def defense_events():
    logs = HFishModel.get_attack_logs(limit=200)
    ai   = AiModel.get_all_analyses()
    events = []
    for log in logs:
        a = ai.get(log.get('attack_ip', ''))
        events.append({
            'id':         log.get('id'),
            'ip':         log.get('attack_ip'),
            'source':     'hfish',
            'ai_score':   80 if a and a.get('decision') == 'true' else 20,
            'ai_reason':  a.get('analysis_text') if a else None,
            'status':     'BLOCKED' if (a and a.get('decision') == 'true') else 'PENDING',
            'created_at': log.get('create_time_str'),
        })
    return ok(events)

@v1.route('/defense/events/<int:event_id>/approve', methods=['POST'])
@require_auth
def event_approve(event_id):
    return ok({'event_id': event_id, 'status': 'APPROVED'})

@v1.route('/defense/events/<int:event_id>/reject', methods=['POST'])
@require_auth
def event_reject(event_id):
    return ok({'event_id': event_id, 'status': 'REJECTED'})

@v1.route('/defense/events/<int:event_id>/false-positive', methods=['POST'])
@require_auth
def event_false_positive(event_id):
    return ok({'event_id': event_id, 'status': 'FALSE_POSITIVE'})

# ─── Scan ─────────────────────────────────────────────────────────────────────
@v1.route('/scan/profiles', methods=['GET'])
@require_auth
def scan_profiles():
    return ok([
        {'key': 'quick',    'name': '快速扫描',   'description': '-sn ping 探测',        'estimated_seconds': 30,  'risk_level': 'low',    'available': True},
        {'key': 'standard', 'name': '标准扫描',   'description': '-sS -T4 -O -sV',       'estimated_seconds': 180, 'risk_level': 'medium', 'available': True},
        {'key': 'vuln',     'name': '漏洞扫描',   'description': '-sV --script vuln',    'estimated_seconds': 600, 'risk_level': 'high',   'available': True},
        {'key': 'full',     'name': '全端口扫描', 'description': '-p- -sV -T4',          'estimated_seconds': 1800,'risk_level': 'high',   'available': True},
    ])

@v1.route('/scan/tasks', methods=['GET'])
@require_auth
def scan_tasks():
    scans = NmapModel.get_scans()
    tasks = [{
        'id':         s.get('id'),
        'target':     s.get('ip_ranges', ''),
        'target_type':'CIDR',
        'tool_name':  'nmap',
        'profile':    'standard',
        'state':      'DONE',
        'priority':   5,
        'started_at': s.get('scan_time'),
        'ended_at':   s.get('scan_time'),
        'created_at': s.get('scan_time'),
    } for s in scans]
    return ok({'items': tasks, 'total': len(tasks)})

@v1.route('/scan/tasks', methods=['POST'])
@require_auth
def scan_task_create():
    body = request.get_json(force=True) or {}
    cfg  = _load_cfg()
    ip_ranges = [body.get('target', '')] if body.get('target') else cfg.get('nmap', {}).get('ip_ranges', [])
    arguments  = cfg.get('nmap', {}).get('arguments', '-sS -T4')

    def _do():
        try:
            nmap_dir = os.path.join(BASE_DIR, 'nmap_plugin')
            if nmap_dir not in sys.path:
                sys.path.insert(0, nmap_dir)
            import network_scan
            network_scan.main(ip_ranges=ip_ranges, scan_args=arguments)
        except Exception as e:
            pass
    threading.Thread(target=_do, daemon=True).start()
    return ok({'state': 'RUNNING', 'message': '扫描任务已启动'})

@v1.route('/scan/findings', methods=['GET'])
@require_auth
def scan_findings():
    vulns = VulnModel.get_vuln_results(limit=500)
    SEV   = {'vulnerable': '高危', 'error': '中危', 'safe': '低危'}
    STA   = {'vulnerable': 'open', 'safe': 'fixed', 'error': 'open'}
    findings = [{
        'id':           i + 1,
        'vuln_name':    v.get('vuln_name', '未知漏洞'),
        'ip':           v.get('ip', v.get('mac_address', '')),
        'port':         None,
        'severity':     SEV.get(v.get('vuln_result', ''), '信息'),
        'status':       STA.get(v.get('vuln_result', ''), 'open'),
        'os_tags':      v.get('os_tags', ''),
        'detail':       v.get('vuln_details', ''),
        'created_at':   v.get('scan_time', ''),
    } for i, v in enumerate(vulns)]
    return ok({'items': findings, 'total': len(findings)})

@v1.route('/scan/findings/<int:finding_id>/status', methods=['PUT'])
@require_auth
def scan_finding_status(finding_id: int):
    # Best-effort update – the DB doesn't expose row IDs, so we return ok()
    return ok()

@v1.route('/scan/assets', methods=['GET'])
@require_auth
def scan_assets():
    assets = NmapModel.get_assets(limit=500)
    return ok({
        'items': [{
            'id':          a.get('id'),
            'target':      a.get('current_ip', ''),
            'target_type': 'IP',
            'tags':        a.get('os_tags', ''),
            'priority':    5,
            'enabled':     True,
            'description': f"{a.get('vendor','')} {a.get('os_type','')}".strip(),
            'created_at':  a.get('first_seen', ''),
        } for a in assets],
        'total': len(assets)
    })

@v1.route('/scan/assets', methods=['POST'])
@require_auth
def scan_asset_create():
    return ok({'id': 0, 'message': '已记录（仅只读）'})

# ─── Firewall ─────────────────────────────────────────────────────────────────
@v1.route('/firewall/config', methods=['GET'])
@require_auth
def firewall_config_get():
    cfg = _load_cfg()
    sw  = (cfg.get('switches') or [{}])[0]
    return ok({
        'enabled':            bool(sw.get('host')),
        'api_base_url':       None,
        'default_vendor':     sw.get('device_type', 'huawei_telnet'),
        'default_policy_id':  str(sw.get('acl_number', '')),
        'timeout_seconds':    30,
        'has_custom_sign_secret': False,
    })

@v1.route('/firewall/config', methods=['POST'])
@require_auth
def firewall_config_save():
    body = request.get_json(force=True) or {}
    cfg  = _load_cfg()
    switches = cfg.setdefault('switches', [{}])
    if not switches:
        switches.append({})
    sw = switches[0]
    if 'default_vendor'    in body: sw['device_type']  = body['default_vendor']
    if 'default_policy_id' in body:
        try: sw['acl_number'] = int(body['default_policy_id'])
        except: pass
    _save_cfg(cfg)
    return ok()

# ─── AI Chat ──────────────────────────────────────────────────────────────────
_chat_sessions: dict[int, list] = {}
_session_counter = 0
_session_lock    = threading.Lock()

def _next_session_id():
    global _session_counter
    with _session_lock:
        _session_counter += 1
        return _session_counter

def _call_ai(messages: list, cfg: dict) -> str:
    import urllib.request
    ai_cfg  = cfg.get('ai', {})
    api_url = ai_cfg.get('api_url', '')
    api_key = ai_cfg.get('api_key', '')
    model   = ai_cfg.get('model', 'gpt-3.5-turbo')
    timeout = int(ai_cfg.get('timeout', 60))
    if not api_url:
        return '⚠️ AI 接口未配置，请在设置中填写 api_url。'
    body = json.dumps({'model': model, 'messages': messages, 'stream': False}).encode()
    req  = urllib.request.Request(api_url, data=body,
                                  headers={'Content-Type': 'application/json',
                                           'Authorization': f'Bearer {api_key}'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return data['choices'][0]['message']['content']
    except Exception as e:
        return f'⚠️ AI 调用失败: {e}'

@v1.route('/ai/sessions', methods=['GET'])
@require_auth
def ai_sessions():
    sessions = [{'id': sid, 'title': f'对话 #{sid}',
                 'context_type': None, 'context_id': None,
                 'operator': g.user.get('username', ''),
                 'started_at': datetime.now().isoformat(),
                 'expires_at': None}
                for sid in _chat_sessions.keys()]
    return ok(sessions)

@v1.route('/ai/sessions/<int:session_id>/messages', methods=['GET'])
@require_auth
def ai_session_messages(session_id: int):
    msgs = _chat_sessions.get(session_id, [])
    return ok([{'role': m['role'], 'content': m['content'],
                'created_at': m.get('ts', datetime.now().isoformat())} for m in msgs])

@v1.route('/ai/sessions/<int:session_id>', methods=['DELETE'])
@require_auth
def ai_session_delete(session_id: int):
    _chat_sessions.pop(session_id, None)
    return ok()

@v1.route('/ai/chat', methods=['POST'])
@require_auth
def ai_chat():
    body       = request.get_json(force=True) or {}
    message    = body.get('message', '').strip()
    session_id = body.get('session_id')
    if not message:
        return err('消息不能为空')

    cfg_load = _load_cfg()
    sys_prompt = cfg_load.get('ai', {}).get('system_prompt',
                     '你是玄枢·AI攻防指挥官，专注于网络安全事件分析、漏洞评估和防御建议。用中文回答，简明扼要。')

    if session_id and session_id in _chat_sessions:
        sid     = session_id
        history = _chat_sessions[sid]
    else:
        sid     = _next_session_id()
        history = [{'role': 'system', 'content': sys_prompt}]
        _chat_sessions[sid] = history

    ts = datetime.now().isoformat()
    history.append({'role': 'user', 'content': message, 'ts': ts})

    cfg_now = _load_cfg()
    reply = _call_ai([{'role': m['role'], 'content': m['content']} for m in history], cfg_now)
    history.append({'role': 'assistant', 'content': reply, 'ts': datetime.now().isoformat()})

    # persist to DB (best effort)
    try:
        AiModel.save_chat_history(message, reply)
    except Exception:
        pass

    return ok({'session_id': sid, 'reply': reply,
               'context': {'type': None, 'id': None}})

# ─── System / Profile ─────────────────────────────────────────────────────────
@v1.route('/system/profile', methods=['GET'])
@require_auth
def system_profile():
    return ok({'username': g.user.get('username'), 'role': g.user.get('role'),
               'permissions': g.user.get('permissions', []), 'email': None, 'full_name': None})

@v1.route('/system/ai-config', methods=['GET'])
@require_auth
def system_ai_config_get():
    cfg = _load_cfg()
    ai  = cfg.get('ai', {})
    return ok({
        'provider':          'openai-compatible',
        'base_url':          ai.get('api_url', ''),
        'model_name':        ai.get('model', ''),
        'enabled':           ai.get('enabled', False),
        'api_key_configured':bool(ai.get('api_key', '')),
    })

@v1.route('/system/ai-config', methods=['POST'])
@require_auth
def system_ai_config_save():
    body = request.get_json(force=True) or {}
    cfg  = _load_cfg()
    ai   = cfg.setdefault('ai', {})
    if 'base_url'    in body: ai['api_url'] = body['base_url']
    if 'model_name'  in body: ai['model']   = body['model_name']
    if 'enabled'     in body: ai['enabled'] = bool(body['enabled'])
    if 'api_key'     in body and body['api_key']: ai['api_key'] = body['api_key']
    _save_cfg(cfg)
    return ok()

@v1.route('/system/ai-prompt', methods=['GET'])
@require_auth
def system_prompt_get():
    cfg = _load_cfg()
    return ok({'prompt': cfg.get('ai', {}).get('system_prompt',
        '你是玄枢·AI攻防指挥官，专注于网络安全事件分析、漏洞评估和防御建议。用中文回答，简明扼要。')})

@v1.route('/system/ai-prompt', methods=['POST'])
@require_auth
def system_prompt_save():
    body = request.get_json(force=True) or {}
    prompt = body.get('prompt', '').strip()
    if not prompt:
        return err('提示词不能为空')
    cfg = _load_cfg()
    cfg.setdefault('ai', {})['system_prompt'] = prompt
    _save_cfg(cfg)
    return ok()

@v1.route('/settings', methods=['GET'])
@require_auth
def settings_get():
    cfg = _load_cfg()
    return ok({
        'hfish': {
            'host_port':     cfg.get('hfish', {}).get('host_port', ''),
            'sync_interval': cfg.get('hfish', {}).get('sync_interval', 60),
            'sync_enabled':  cfg.get('hfish', {}).get('sync_enabled', False),
        },
        'nmap': {
            'ip_ranges':            cfg.get('nmap', {}).get('ip_ranges', []),
            'arguments':            cfg.get('nmap', {}).get('arguments', '-sS -O -T4'),
            'scan_interval':        cfg.get('nmap', {}).get('scan_interval', 604800),
            'scan_enabled':         cfg.get('nmap', {}).get('scan_enabled', False),
            'vuln_scripts_by_tag':  cfg.get('nmap', {}).get('vuln_scripts_by_tag', {}),
        },
        'logging': cfg.get('logging', {}),
    })

@v1.route('/settings', methods=['POST'])
@require_auth
def settings_save():
    body = request.get_json(force=True) or {}
    cfg  = _load_cfg()
    if 'hfish' in body:
        h = body['hfish']
        cfg.setdefault('hfish', {}).update({
            'host_port':    h.get('host_port',    cfg.get('hfish', {}).get('host_port', '')),
            'sync_interval':int(h.get('sync_interval', 60)),
            'sync_enabled': bool(h.get('sync_enabled', False)),
        })
        if h.get('api_key'): cfg['hfish']['api_key'] = h['api_key']
    if 'nmap' in body:
        n = body['nmap']
        ranges = n.get('ip_ranges', [])
        if isinstance(ranges, str):
            ranges = [r.strip() for r in ranges.split(',') if r.strip()]
        cfg.setdefault('nmap', {}).update({
            'ip_ranges':           ranges,
            'arguments':           n.get('arguments', '-sS -O -T4'),
            'scan_interval':       int(n.get('scan_interval', 604800)),
            'scan_enabled':        bool(n.get('scan_enabled', False)),
            'vuln_scripts_by_tag': n.get('vuln_scripts_by_tag', {}),
        })
    if 'logging' in body:
        cfg['logging'] = {**cfg.get('logging', {}), **body['logging']}
    _save_cfg(cfg)
    return ok()

# ─── Audit ────────────────────────────────────────────────────────────────────
@v1.route('/audit/logs', methods=['GET'])
@require_auth
def audit_logs():
    logs  = HFishModel.get_attack_logs(limit=200)
    chats = AiModel.get_chat_history(limit=50)
    items = []
    for log in logs:
        items.append({
            'id':         log.get('id'),
            'operator':   log.get('attack_ip', ''),
            'action':     f"{log.get('service_name','')} 攻击",
            'resource':   f"蜜罐/{log.get('service_name','')}",
            'result':     log.get('threat_level', 'info'),
            'ip':         log.get('attack_ip', ''),
            'created_at': log.get('create_time_str', ''),
        })
    for chat in chats:
        items.append({
            'id':         f"chat-{chat.get('id')}",
            'operator':   g.user.get('username', 'operator'),
            'action':     str(chat.get('query', ''))[:80],
            'resource':   'AI对话',
            'result':     'success',
            'ip':         '',
            'created_at': chat.get('create_time', ''),
        })
    items.sort(key=lambda x: str(x.get('created_at', '')), reverse=True)
    return ok({'items': items[:200], 'total': len(items)})

# ─── Threat Intel  (lightweight stubs) ────────────────────────────────────────
@v1.route('/threat-intel/overview', methods=['GET'])
@require_auth
def ti_overview():
    vulns = VulnModel.get_vuln_results(limit=500)
    cves  = [v['vuln_name'] for v in vulns if v.get('vuln_name', '').startswith('CVE')]
    return ok({'total_cves': len(set(cves)), 'kev_hits': 0, 'epss_top10': [],
               'findings_total': len(vulns), 'enriched_count': 0})

@v1.route('/threat-intel/sources', methods=['GET'])
@require_auth
def ti_sources():
    return ok([
        {'id': 1, 'name': 'NVD',    'source_type': 'cve',  'enabled': True,  'last_sync': None},
        {'id': 2, 'name': 'CISA KEV','source_type': 'kev', 'enabled': False, 'last_sync': None},
    ])

@v1.route('/threat-intel/cve/<cve_id>', methods=['GET'])
@require_auth
def ti_cve(cve_id: str):
    return ok({'vuln_id': cve_id, 'cvss_score': None, 'cvss_vector': None,
               'epss_score': None, 'is_in_kev': False, 'affected_versions': None,
               'exploit_available': False, 'exploit_sources': None})

@v1.route('/threat-intel/ip/<ip>', methods=['GET'])
@require_auth
def ti_ip(ip: str):
    a = AiModel.get_analysis_by_ip(ip)
    return ok({'found': bool(a), 'data': a or {}})

@v1.route('/threat-intel/iocs', methods=['GET'])
@require_auth
def ti_iocs():
    logs = HFishModel.get_attack_logs(limit=200)
    seen: set = set()
    iocs = []
    for log in logs:
        ip = log.get('attack_ip', '')
        if ip and ip not in seen:
            seen.add(ip)
            a = AiModel.get_analysis_by_ip(ip)
            score = 85 if a and a.get('decision') == 'true' else 30
            iocs.append({
                'id':       log.get('id'),
                'type':     'IP',
                'value':    ip,
                'score':    score,
                'source':   'HFish',
                'tags':     [log.get('service_name', '')] if log.get('service_name') else [],
                'location': log.get('ip_location', ''),
                'last_seen':log.get('create_time_str', ''),
            })
    return ok({'items': iocs, 'total': len(iocs)})

# ─── Honeypots  (in-memory store) ─────────────────────────────────────────────
_honeypots: list[dict] = []
_hp_counter = 0

@v1.route('/honeypots', methods=['GET'])
@require_auth
def honeypots_list():
    return ok({'items': _honeypots, 'total': len(_honeypots)})

@v1.route('/honeypots', methods=['POST'])
@require_auth
def honeypots_create():
    global _hp_counter
    body = request.get_json(force=True) or {}
    _hp_counter += 1
    hp = {'id': _hp_counter, 'name': body.get('name', f'蜜罐#{_hp_counter}'),
          'honeypot_type': body.get('honeypot_type', 'custom'),
          'target_service': body.get('target_service', ''),
          'bait_data': body.get('bait_data', ''),
          'status': 'ACTIVE', 'managed_by': 'manual',
          'created_at': datetime.now().isoformat(),
          'updated_at': datetime.now().isoformat()}
    _honeypots.append(hp)
    return ok(hp), 201

@v1.route('/honeypots/<int:hp_id>', methods=['PUT'])
@require_auth
def honeypots_update(hp_id: int):
    body = request.get_json(force=True) or {}
    for hp in _honeypots:
        if hp['id'] == hp_id:
            hp.update({k: v for k, v in body.items() if k != 'id'})
            hp['updated_at'] = datetime.now().isoformat()
            return ok(hp)
    return err('蜜罐不存在', 404)

@v1.route('/honeypots/<int:hp_id>', methods=['DELETE'])
@require_auth
def honeypots_delete(hp_id: int):
    global _honeypots
    _honeypots = [h for h in _honeypots if h['id'] != hp_id]
    return ok()

@v1.route('/honeypots/<int:hp_id>/alerts', methods=['GET'])
@require_auth
def honeypots_alerts(hp_id: int):
    return ok({'items': [], 'total': 0})

# ─── Workflows  (stubs) ───────────────────────────────────────────────────────
@v1.route('/workflows', methods=['GET'])
@require_auth
def workflows_list():
    return ok({'items': [], 'total': 0})

@v1.route('/workflows/runs', methods=['GET'])
@require_auth
def workflow_runs():
    return ok({'items': [], 'total': 0})

# ─── Nmap legacy bridge (/api/nmap/ wrappers under /api/v1/ namespace) ────────
@v1.route('/nmap/scans', methods=['GET'])
@require_auth
def v1_nmap_scans():
    return ok(NmapModel.get_scans())

@v1.route('/nmap/hosts', methods=['GET'])
@require_auth
def v1_nmap_hosts():
    limit   = int(request.args.get('limit', 500))
    scan_id = request.args.get('scan_id')
    hosts   = NmapModel.get_hosts(scan_id=int(scan_id) if scan_id else None, limit=limit)
    for h in hosts:
        for key in ('open_ports', 'services'):
            if isinstance(h.get(key), str) and h[key]:
                try:
                    h[key] = json.loads(h[key])
                except Exception:
                    h[key] = [p.strip() for p in h[key].split(',') if p.strip()]
    return ok(hosts)

@v1.route('/nmap/host/<ip>', methods=['GET'])
@require_auth
def v1_nmap_host(ip: str):
    h = NmapModel.get_host_by_ip(ip)
    if h:
        for key in ('open_ports', 'services'):
            if isinstance(h.get(key), str) and h[key]:
                try:
                    h[key] = json.loads(h[key])
                except Exception:
                    h[key] = [p.strip() for p in h[key].split(',') if p.strip()]
    return ok(h)
