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
    NmapModel, VulnModel, HFishModel, AiModel
)
from utils.logger import log as unified_log

CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

def _load_cfg():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def _save_cfg(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ─── Blueprint ────────────────────────────────────────────────────────────────
v1 = Blueprint('v1', __name__, url_prefix='/api/v1')
legacy_api = Blueprint('legacy_api', __name__, url_prefix='/api')

# ─── Simple JWT (stdlib only) ─────────────────────────────────────────────────
_JWT_SECRET = os.environ.get('AIMIGUARD_SECRET', 'aimiguard-secret-key-2026')
_JWT_TTL    = 86400 * 7  # 7 days

# 登录校验失败时使用的默认账号（仅用于首次启动或未配置 users 的场景）
_DEFAULT_USERS = [{'username': 'admin', 'password': 'admin123', 'role': 'admin'}]

def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

def _b64d(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + '=' * (pad % 4))

def _now_iso() -> str:
    """统一生成 ISO 时间戳，避免各处重复 datetime.now().isoformat()。"""
    return datetime.now().isoformat()

def _body() -> dict:
    """统一读取 JSON 请求体；空体、解析失败均回落为空字典。"""
    return request.get_json(force=True) or {}

def _as_bool(value) -> bool:
    """兼容多种布尔入参（字符串/数字/布尔）。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'yes', 'on')
    return bool(value)

def _parse_int_arg(name: str, default: int) -> int:
    """读取 query 参数中的整数值；非法值自动回落默认值。"""
    raw = request.args.get(name, default)
    try:
        return int(raw)
    except Exception:
        return default

def _run_daemon(task):
    """将耗时任务以守护线程方式触发，避免阻塞请求。"""
    threading.Thread(target=task, daemon=True).start()

def _normalize_host_fields(host: dict | None) -> dict | None:
    """兼容 open_ports/services 字段的历史格式（JSON 字符串或逗号分隔）。"""
    if not host:
        return host
    for key in ('open_ports', 'services'):
        value = host.get(key)
        if isinstance(value, str) and value:
            try:
                host[key] = json.loads(value)
            except Exception:
                host[key] = [p.strip() for p in value.split(',') if p.strip()]
    return host


def _read_chat_system_prompt(cfg: dict) -> tuple[str, bool]:
    """从 ai.analysis_map 读取聊天系统提示词，并兼容迁移旧字段。"""
    ai_cfg = cfg.setdefault('ai', {})
    analysis_map = ai_cfg.setdefault('analysis_map', {})

    prompt = (analysis_map.get('chat_system_prompt') or '').strip()
    if prompt:
        return prompt, False

    legacy_prompt = (ai_cfg.get('system_prompt') or '').strip()
    if legacy_prompt:
        analysis_map['chat_system_prompt'] = legacy_prompt
        ai_cfg.pop('system_prompt', None)
        return legacy_prompt, True

    return '', False


# ─── Runtime workers (migrated from web_app) ─────────────────────────────────
_is_scanning = False
_is_vuln_scanning = False
_sync_thread_started = False
_scan_thread_started = False


def _runtime_log(level: str, msg: str):
    """统一后台任务日志输出。"""
    unified_log('Runtime', msg, level.upper())


def get_runtime_scan_status() -> dict:
    return {
        'is_scanning': _is_scanning,
        'is_vuln_scanning': _is_vuln_scanning,
    }


def run_nmap_scan(ip_ranges, arguments):
    """后台执行一次 Nmap 扫描。"""
    global _is_scanning
    if _is_scanning:
        return

    _is_scanning = True
    try:
        nmap_dir = os.path.join(BASE_DIR, 'plugin', 'nmap_plugin')
        if nmap_dir not in sys.path:
            sys.path.insert(0, nmap_dir)
        import network_scan
        network_scan.main(ip_ranges=ip_ranges, scan_args=arguments, scan_interval=0)
    except Exception as e:
        _runtime_log('error', f'Nmap 扫描执行失败: {e}')
    finally:
        _is_scanning = False


def run_vuln_scan_task():
    """后台执行一次漏洞扫描任务。"""
    global _is_vuln_scanning
    if _is_vuln_scanning:
        return

    _is_vuln_scanning = True
    try:
        hosts_data = NmapModel.get_latest_up_hosts()
        if not hosts_data:
            _runtime_log('warn', '漏洞扫描跳过: 没有在线主机')
            return

        nmap_dir = os.path.join(BASE_DIR, 'plugin', 'nmap_plugin')
        if nmap_dir not in sys.path:
            sys.path.insert(0, nmap_dir)
        import network_scan
        stats = network_scan.run_vuln_scan(hosts_data)
        _runtime_log('info', f'漏洞扫描完成: {stats}')
    except Exception as e:
        _runtime_log('error', f'漏洞扫描执行失败: {e}')
    finally:
        _is_vuln_scanning = False


def run_hfish_sync():
    """执行一次 HFish 同步并触发 AI 分析。"""
    try:
        hfish_dir = os.path.join(BASE_DIR, 'plugin', 'hfish')
        if hfish_dir not in sys.path:
            sys.path.insert(0, hfish_dir)
        from attack_log_sync import get_attack_logs
        from plugin.hfish.ai_analyzer import analyze_and_ban

        cfg = _load_cfg()
        host_port = cfg.get('hfish', {}).get('host_port', '')
        api_key = cfg.get('hfish', {}).get('api_key', '')
        last_timestamp = HFishModel.get_last_timestamp()
        logs = get_attack_logs(last_timestamp, 0, host_port, api_key)

        if not logs:
            _runtime_log('info', 'HFish 同步完成: 无新数据')
            return {'success': True, 'total': 0, 'new': 0}

        count = HFishModel.save_logs(logs)
        _runtime_log('info', f'HFish 同步完成: 获取 {len(logs)} 条, 新增 {count} 条')

        if count > 0:
            ip_logs: dict[str, list] = {}
            for log in logs:
                ip = log.get('attack_ip')
                if not ip:
                    continue
                ip_logs.setdefault(ip, []).append(log)

            for ip, ip_log_list in ip_logs.items():
                _run_daemon(lambda ip=ip, logs=ip_log_list, cfg=cfg: analyze_and_ban(ip, logs, cfg))

        return {'success': True, 'total': len(logs), 'new': count}
    except Exception as e:
        _runtime_log('error', f'HFish 同步失败: {e}')
        return {'success': False, 'error': str(e)}


def run_hfish_sync_loop():
    """持续执行 HFish 同步。"""
    while True:
        try:
            cfg = _load_cfg()
            if not cfg.get('hfish', {}).get('sync_enabled', False):
                time.sleep(10)
                continue
            run_hfish_sync()
            time.sleep(int(cfg.get('hfish', {}).get('sync_interval', 60)))
        except Exception as e:
            _runtime_log('error', f'HFish 持续同步异常: {e}')
            time.sleep(10)


def run_nmap_scan_loop():
    """持续执行 Nmap 定时扫描。"""
    time.sleep(5)
    while True:
        try:
            cfg = _load_cfg()
            ncfg = cfg.get('nmap', {})
            if not ncfg.get('scan_enabled', False):
                time.sleep(10)
                continue

            scan_interval = ncfg.get('scan_interval')
            ip_ranges = ncfg.get('ip_ranges')
            arguments = ncfg.get('arguments')
            if scan_interval is None or not ip_ranges or not arguments:
                time.sleep(10)
                continue
            if _is_scanning:
                time.sleep(10)
                continue

            run_nmap_scan(ip_ranges, arguments)
            time.sleep(int(scan_interval))
        except Exception as e:
            _runtime_log('error', f'Nmap 定时扫描异常: {e}')
            time.sleep(10)


def start_runtime_workers():
    """按配置启动后台同步与扫描线程（幂等）。"""
    global _sync_thread_started, _scan_thread_started
    cfg = _load_cfg()

    if cfg.get('hfish', {}).get('sync_enabled', False) and not _sync_thread_started:
        _run_daemon(run_hfish_sync_loop)
        _sync_thread_started = True
        _runtime_log('info', 'HFish 同步线程已启动')

    if cfg.get('nmap', {}).get('scan_enabled', False) and not _scan_thread_started:
        _run_daemon(run_nmap_scan_loop)
        _scan_thread_started = True
        _runtime_log('info', 'Nmap 扫描线程已启动')

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
    """简单 Bearer 认证装饰器：解码失败即返回 401。"""
    @wraps(f)
    def wrapped(*args, **kwargs):
        header = request.headers.get('Authorization', '')
        token  = header.removeprefix('Bearer ').strip()
        if request.path == '/api/v1/ai/chat':
            auth_header = request.headers.get('Authorization', '')
            unified_log(
                'AIChat',
                f'入口命中 path={request.path} from={request.remote_addr} pid={os.getpid()} auth={"yes" if auth_header else "no"}',
                'INFO'
            )
        payload = _decode_token(token)
        if payload is None:
            if request.path == '/api/v1/ai/chat':
                unified_log('AIChat', '鉴权失败: token 缺失、格式错误或已过期', 'WARN')
            return jsonify({'code': 401, 'message': '未授权'}), 401
        g.user = payload
        return f(*args, **kwargs)
    return wrapped

def ok(data=None, **extra):
    """统一成功响应结构，便于前端一致处理。"""
    return jsonify({'code': 0, 'message': 'ok', 'data': data, **extra})

def err(msg, code=400):
    """统一错误响应结构。"""
    return jsonify({'code': code, 'message': msg}), code

# ─── Auth ─────────────────────────────────────────────────────────────────────
@v1.route('/auth/login', methods=['POST'])
def auth_login():
    # 登录仅做本地配置校验，不依赖外部认证中心。
    body = _body()
    username = body.get('username', '').strip()
    password = body.get('password', '').strip()

    # 凭据来源优先级：config.json 的 users > 默认管理员账号
    cfg = _load_cfg()
    users = cfg.get('users', _DEFAULT_USERS)
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
    # 该接口用于首页总览卡片，聚合多个模型统计结果。
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
    # 支持普通明细和按攻击 IP 聚合两种视图。
    limit       = _parse_int_arg('limit', 200)
    offset      = _parse_int_arg('offset', 0)
    aggregated  = _as_bool(request.args.get('aggregated', '0'))
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
    # 手动触发一次同步，不等待执行结束（异步 best-effort）。
    # 复用 run_hfish_sync 逻辑（HFishSyncer 已废弃，与 run_hfish_sync_loop 保持一致）
    def _do():
        try:
            run_hfish_sync()
        except Exception:
            pass
    _run_daemon(_do)
    return ok({'message': '同步任务已触发'})

@v1.route('/defense/hfish/test', methods=['POST'])
@require_auth
def defense_hfish_test():
    """测试 HFish 连通性（不写库）。"""
    body = _body()
    cfg  = _load_cfg()
    hcfg = cfg.get('hfish', {})
    host_port = (body.get('host_port') or hcfg.get('host_port') or '').strip()
    api_key   = (body.get('api_key') or hcfg.get('api_key') or '').strip()
    if not host_port or not api_key:
        return err('请先填写 HFish 地址和 API Key', 400)

    try:
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        url = f"https://{host_port}/api/v1/attack/detail?api_key={api_key}"
        payload = {
            'start_time': int(time.time()) - 60,
            'end_time': 0,
            'page_no': 1,
            'page_size': 1,
            'intranet': -1,
            'threat_label': [],
            'client_id': [],
            'service_name': [],
            'info_confirm': '0',
        }
        resp = requests.post(url, json=payload, verify=False, timeout=15)
        resp.raise_for_status()
        _ = resp.json()
        return ok({'reachable': True, 'host_port': host_port})
    except Exception as e:
        return err(f'HFish 连接失败: {e}', 502)

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
    body = _body()
    cfg  = _load_cfg()
    h    = cfg.setdefault('hfish', {})
    if 'host_port'     in body: h['host_port']      = body['host_port']
    if 'api_key'       in body: h['api_key']         = body['api_key']
    if 'sync_interval' in body: h['sync_interval']   = int(body['sync_interval'])
    if 'enabled'       in body: h['sync_enabled']    = _as_bool(body['enabled'])
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
    body = _body()
    cfg  = _load_cfg()
    ip_ranges = [body.get('target', '')] if body.get('target') else cfg.get('nmap', {}).get('ip_ranges', [])
    arguments  = cfg.get('nmap', {}).get('arguments', '-sS -T4')

    def _do():
        try:
            nmap_dir = os.path.join(BASE_DIR, 'plugin', 'nmap_plugin')
            if nmap_dir not in sys.path:
                sys.path.insert(0, nmap_dir)
            import network_scan
            network_scan.main(ip_ranges=ip_ranges, scan_args=arguments)
        except Exception:
            pass
    _run_daemon(_do)
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

# ─── AI Chat ──────────────────────────────────────────────────────────────────
_chat_sessions: dict[int, list] = {}
_session_counter = 0
_session_lock    = threading.Lock()

def _next_session_id():
    """线程安全地分配会话 ID。"""
    global _session_counter
    with _session_lock:
        _session_counter += 1
        return _session_counter

def _ai_diag(cfg: dict, message: str, level: str = 'INFO'):
    """统一 AI 诊断日志输出，便于定位配置与网关问题。"""
    try:
        enabled = cfg.get('logging', {}).get('ai_log', True)
    except Exception:
        enabled = True
    if enabled:
        unified_log('AIChat', message, level)

def _call_ai(messages: list, cfg: dict, tools: list | None = None) -> dict:
    """调用 OpenAI-compatible 接口，返回 {content, tool_calls}。"""
    import urllib.error
    import urllib.request
    from json import JSONDecodeError

    def _candidate_chat_urls(raw_url: str) -> list[str]:
        """生成候选地址并按顺序尝试，兼容不同网关的 URL 约定。"""
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

        # 去重且保持顺序。
        seen = set()
        ordered = []
        for item in cands:
            if item and item not in seen:
                ordered.append(item)
                seen.add(item)
        return ordered

    ai_cfg  = cfg.get('ai', {})
    api_url = ai_cfg.get('api_url', '')
    api_key = ai_cfg.get('api_key', '')
    model   = ai_cfg.get('model', 'gpt-3.5-turbo')
    timeout = int(ai_cfg.get('timeout', 60))
    endpoints = _candidate_chat_urls(api_url)
    if not endpoints:
        _ai_diag(cfg, f'AI 接口未配置，config={CONFIG_FILE}', 'WARN')
        return {'content': '⚠️ AI 接口未配置，请在设置中填写 api_url。', 'tool_calls': []}

    _ai_diag(cfg, f'配置来源: config={CONFIG_FILE} | module={__file__} | python={sys.executable}')
    _ai_diag(cfg, f'AI 请求候选 endpoint: {" | ".join(endpoints)}')

    req_body: dict = {'model': model, 'messages': messages, 'stream': False}
    if tools:
        req_body['tools'] = tools
        req_body['tool_choice'] = 'auto'
    body = json.dumps(req_body).encode()
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    last_http_error: str | None = None
    last_parse_error: str | None = None
    for endpoint in endpoints:
        req = urllib.request.Request(endpoint, data=body, headers=headers)
        _ai_diag(cfg, f'尝试请求 endpoint={endpoint}')
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status_code = getattr(resp, 'status', None) or getattr(resp, 'code', None)
                raw_bytes = resp.read()
                raw_text = raw_bytes.decode('utf-8', errors='ignore').strip()
                content_type = ''
                try:
                    content_type = resp.headers.get('Content-Type', '') or ''
                except Exception:
                    content_type = ''

                _ai_diag(cfg, f'AI 响应成功 endpoint={endpoint} status={status_code} content-type={content_type}')

                # 某些网关会在错误路径返回 HTML 200，这里做显式拦截并回退下一个候选地址。
                if not raw_text:
                    last_parse_error = f'空响应 @ {endpoint}'
                    _ai_diag(cfg, f'AI 响应为空 endpoint={endpoint}', 'WARN')
                    continue

                try:
                    data = json.loads(raw_text)
                except JSONDecodeError:
                    snippet = raw_text[:200].replace('\n', ' ')
                    last_parse_error = f'非 JSON 响应 @ {endpoint}: {snippet}'
                    _ai_diag(cfg, f'AI 非 JSON 响应 endpoint={endpoint} snippet={snippet}', 'WARN')
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
                    _ai_diag(cfg, f'AI JSON 结构异常 endpoint={endpoint} body={preview}', 'WARN')
                    continue
        except urllib.error.HTTPError as e:
            detail = ''
            try:
                detail = e.read().decode('utf-8', errors='ignore')
            except Exception:
                pass

            _ai_diag(cfg, f'AI 响应失败 endpoint={endpoint} status={e.code} reason={e.reason}', 'WARN')

            if e.code == 404:
                last_http_error = f'HTTP 404 Not Found @ {endpoint}'
                continue

            if detail:
                return {'content': f'⚠️ AI 调用失败: HTTP {e.code} {e.reason} - {detail[:300]}', 'tool_calls': []}
            return {'content': f'⚠️ AI 调用失败: HTTP {e.code} {e.reason}', 'tool_calls': []}
        except Exception as e:
            _ai_diag(cfg, f'AI 请求异常 endpoint={endpoint} error={e}', 'ERROR')
            return {'content': f'⚠️ AI 调用失败: {e}', 'tool_calls': []}

    if last_http_error:
        _ai_diag(cfg, f'AI 请求最终失败: {last_http_error}', 'ERROR')
        return {'content': f'⚠️ AI 调用失败: {last_http_error}（已尝试: {", ".join(endpoints)}）', 'tool_calls': []}
    if last_parse_error:
        _ai_diag(cfg, f'AI 请求最终失败: {last_parse_error}', 'ERROR')
        return {'content': f'⚠️ AI 调用失败: {last_parse_error}', 'tool_calls': []}
    _ai_diag(cfg, 'AI 请求最终失败: 未知错误', 'ERROR')
    return {'content': '⚠️ AI 调用失败: 未知错误。', 'tool_calls': []}

@v1.route('/ai/sessions', methods=['GET'])
@require_auth
def ai_sessions():
    # 会话为内存态，服务重启后会清空。
    sessions = [{'id': sid, 'title': f'对话 #{sid}',
                 'context_type': None, 'context_id': None,
                 'operator': g.user.get('username', ''),
                 'started_at': _now_iso(),
                 'expires_at': None}
                for sid in _chat_sessions.keys()]
    return ok(sessions)

@v1.route('/ai/sessions/<int:session_id>/messages', methods=['GET'])
@require_auth
def ai_session_messages(session_id: int):
    """返回会话消息列表，仅包含前端可展示的 user/assistant 消息。"""
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

@v1.route('/ai/sessions/<int:session_id>', methods=['DELETE'])
@require_auth
def ai_session_delete(session_id: int):
    _chat_sessions.pop(session_id, None)
    return ok()

@v1.route('/ai/chat', methods=['POST'])
@require_auth
def ai_chat():
    # 当前实现将上下文保存在进程内存，适合单实例轻量部署。
    unified_log(
        'AIChat',
        f'收到 /api/v1/ai/chat 请求 from={request.remote_addr} pid={os.getpid()} config={CONFIG_FILE}',
        'INFO'
    )
    body       = _body()
    message    = body.get('message', '').strip()
    session_id = body.get('session_id')
    if not message:
        return err('消息不能为空')

    cfg_load = _load_cfg()
    sys_prompt, migrated = _read_chat_system_prompt(cfg_load)
    if migrated:
        _save_cfg(cfg_load)

    if session_id and session_id in _chat_sessions:
        sid     = session_id
        history = _chat_sessions[sid]
    else:
        sid     = _next_session_id()
        history = [{'role': 'system', 'content': sys_prompt}] if sys_prompt else []
        _chat_sessions[sid] = history

    ts = _now_iso()
    history.append({'role': 'user', 'content': message, 'ts': ts})

    cfg_now = _load_cfg()

    # ── 工具定义（可扩展：新增工具只需在此列表追加 schema 并在 _TOOL_HANDLERS 注册）
    _TOOL_DEFS = [
        {
            'type': 'function',
            'function': {
                'name': 'nmap_scan',
                'description': '执行 Nmap 网络扫描，返回主机与端口信息',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'target': {
                            'type': 'string',
                            'description': '目标 IP、域名或网段，如 192.168.1.0/24'
                        },
                        'arguments': {
                            'type': 'string',
                            'description': 'nmap 参数，如 -sV -T4，默认 -sV -O -T4'
                        }
                    },
                    'required': ['target']
                }
            }
        }
    ]

    def _exec_nmap_scan(args: dict) -> str:
        """执行真实 nmap 扫描并写库，返回 JSON 字符串。"""
        try:
            from plugin.nmap_plugin.network_scan import scan_hosts, parse_scan_results
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
            # 写库（与 network_scan.save_to_db 逻辑一致）
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

    # ── 第一次调用，携带工具定义
    msgs_for_ai = [{'role': m['role'], 'content': m.get('content') or ''}
                   for m in history
                   if m['role'] in ('system', 'user', 'assistant')]
    result = _call_ai(msgs_for_ai, cfg_now, tools=_TOOL_DEFS)
    content = result.get('content', '')
    tool_calls = result.get('tool_calls', [])

    if content.startswith('⚠️'):
        unified_log('AIChat', f'AI 回复异常: {content[:240]}', 'WARN')

    if tool_calls:
        # 将带 tool_calls 的 assistant 消息追加到历史
        history.append({
            'role': 'assistant',
            'content': content,
            'tool_calls': tool_calls,
            'ts': _now_iso()
        })
        # 逐个执行工具调用
        for tc in tool_calls:
            func_name = tc.get('name', '')
            handler = _TOOL_HANDLERS.get(func_name)
            if handler:
                tool_result = handler(tc.get('arguments', {}))
            else:
                tool_result = json.dumps({'error': f'未知工具: {func_name}'}, ensure_ascii=False)
            history.append({
                'role': 'tool',
                'tool_call_id': tc.get('id', ''),
                'name': func_name,
                'content': tool_result,
                'ts': _now_iso()
            })
        # 第二次调用，获取最终自然语言回答
        msgs_for_ai2 = []
        for m in history:
            if m['role'] == 'tool':
                msgs_for_ai2.append({
                    'role': 'tool',
                    'tool_call_id': m.get('tool_call_id', ''),
                    'name': m.get('name', ''),
                    'content': m.get('content', '')
                })
            elif m['role'] == 'assistant' and m.get('tool_calls'):
                msgs_for_ai2.append({
                    'role': 'assistant',
                    'content': m.get('content') or '',
                    'tool_calls': [
                        {
                            'id': t['id'],
                            'type': 'function',
                            'function': {
                                'name': t['name'],
                                'arguments': json.dumps(t['arguments'], ensure_ascii=False)
                            }
                        } for t in m['tool_calls']
                    ]
                })
            else:
                msgs_for_ai2.append({'role': m['role'], 'content': m.get('content') or ''})
        result2 = _call_ai(msgs_for_ai2, cfg_now)
        reply = result2.get('content', '')
        if reply.startswith('⚠️'):
            unified_log('AIChat', f'AI 二次回复异常: {reply[:240]}', 'WARN')
        history.append({'role': 'assistant', 'content': reply, 'ts': _now_iso()})
    else:
        reply = content
        history.append({'role': 'assistant', 'content': reply, 'ts': _now_iso()})

    # 额外做一份数据库持久化，失败不影响主流程。
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
        'provider':          ai.get('provider', 'openai-compatible'),
        'base_url':          ai.get('api_url', ''),
        'model':             ai.get('model', ''),
        'model_name':        ai.get('model', ''),
        'enabled':           ai.get('enabled', False),
        'auto_ban':          ai.get('auto_ban', False),
        'ban_threshold':     ai.get('ban_threshold', 80),
        'api_key_configured':bool(ai.get('api_key', '')),
    })

@v1.route('/system/ai-config', methods=['POST'])
@require_auth
def system_ai_config_save():
    body = _body()
    cfg  = _load_cfg()
    ai   = cfg.setdefault('ai', {})
    if 'provider'    in body: ai['provider'] = body['provider']
    if 'base_url'    in body: ai['api_url'] = body['base_url']
    # 兼容前端两种命名：model / model_name
    if 'model'       in body: ai['model']   = body['model']
    if 'model_name'  in body: ai['model']   = body['model_name']
    if 'enabled'     in body: ai['enabled'] = _as_bool(body['enabled'])
    if 'auto_ban'    in body: ai['auto_ban'] = _as_bool(body['auto_ban'])
    if 'ban_threshold' in body:
        try:
            ai['ban_threshold'] = int(body['ban_threshold'])
        except Exception:
            pass
    if 'api_key'     in body and body['api_key']: ai['api_key'] = body['api_key']
    _save_cfg(cfg)
    return ok()

@v1.route('/system/ai-prompt', methods=['GET'])
@require_auth
def system_prompt_get():
    cfg = _load_cfg()
    prompt, migrated = _read_chat_system_prompt(cfg)
    if migrated:
        _save_cfg(cfg)
    return ok({'prompt': prompt})

@v1.route('/system/ai-prompt', methods=['POST'])
@require_auth
def system_prompt_save():
    body = _body()
    prompt = body.get('prompt', '').strip()
    if not prompt:
        return err('提示词不能为空')
    cfg = _load_cfg()
    ai_cfg = cfg.setdefault('ai', {})
    ai_cfg.setdefault('analysis_map', {})['chat_system_prompt'] = prompt
    ai_cfg.pop('system_prompt', None)
    _save_cfg(cfg)
    return ok()

@v1.route('/settings', methods=['GET'])
@require_auth
def settings_get():
    cfg = _load_cfg()
    return ok({
        'hfish': {
            'host_port':     cfg.get('hfish', {}).get('host_port', ''),
            'api_base_url':  cfg.get('hfish', {}).get('api_base_url', ''),
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
    # 设置保存接口尽量兼容前端不同字段命名和布尔表达方式。
    body = _body()
    cfg  = _load_cfg()
    if 'hfish' in body:
        h = body['hfish']
        sync_enabled = h.get('sync_enabled', h.get('enabled', cfg.get('hfish', {}).get('sync_enabled', False)))
        cfg.setdefault('hfish', {}).update({
            'host_port':    h.get('host_port',    cfg.get('hfish', {}).get('host_port', '')),
            'sync_interval':int(h.get('sync_interval', 60)),
            'sync_enabled': _as_bool(sync_enabled),
        })
        if 'api_base_url' in h: cfg['hfish']['api_base_url'] = h.get('api_base_url', '')
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
            'scan_enabled':        _as_bool(n.get('scan_enabled', False)),
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
    body = _body()
    _hp_counter += 1
    hp = {'id': _hp_counter, 'name': body.get('name', f'蜜罐#{_hp_counter}'),
          'honeypot_type': body.get('honeypot_type', 'custom'),
          'target_service': body.get('target_service', ''),
          'bait_data': body.get('bait_data', ''),
          'status': 'ACTIVE', 'managed_by': 'manual',
          'created_at': _now_iso(),
          'updated_at': _now_iso()}
    _honeypots.append(hp)
    return ok(hp), 201

@v1.route('/honeypots/<int:hp_id>', methods=['PUT'])
@require_auth
def honeypots_update(hp_id: int):
    body = _body()
    for hp in _honeypots:
        if hp['id'] == hp_id:
            hp.update({k: v for k, v in body.items() if k != 'id'})
            hp['updated_at'] = _now_iso()
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

# ─── Nmap legacy bridge (/api/nmap/ wrappers under /api/v1/ namespace) ────────
@v1.route('/nmap/scans', methods=['GET'])
@require_auth
def v1_nmap_scans():
    return ok(NmapModel.get_scans())

@v1.route('/nmap/hosts', methods=['GET'])
@require_auth
def v1_nmap_hosts():
    # 历史数据里端口/服务字段格式不一，这里做统一归一化。
    limit   = _parse_int_arg('limit', 500)
    scan_id = request.args.get('scan_id')
    hosts   = NmapModel.get_hosts(scan_id=int(scan_id) if scan_id else None, limit=limit)
    for h in hosts:
        _normalize_host_fields(h)
    return ok(hosts)

@v1.route('/nmap/host/<ip>', methods=['GET'])
@require_auth
def v1_nmap_host(ip: str):
    h = NmapModel.get_host_by_ip(ip)
    return ok(_normalize_host_fields(h))


# ─── Legacy /api compatibility layer ─────────────────────────────────────────
# Keep old endpoints alive while moving implementation ownership into api_v1.


def _legacy_module_status(cfg: dict) -> dict:
    ai_cfg = cfg.get('ai', {})
    ai_enabled = ai_cfg.get('enabled', False)
    auto_ban = ai_cfg.get('auto_ban', False)
    switches = cfg.get('switches', [])
    return {
        'hfish_sync': cfg.get('hfish', {}).get('sync_enabled', False),
        'nmap_scan': cfg.get('nmap', {}).get('scan_enabled', False),
        'ai_analysis': ai_enabled,
        'acl_auto_ban': bool(ai_enabled and auto_ban and switches),
    }


def _legacy_safe_ai(cfg: dict) -> dict:
    ai = cfg.get('ai', {}).copy()
    ai.pop('api_key', None)
    return ai


@legacy_api.route('/status', methods=['GET'])
@require_auth
def legacy_status():
    return jsonify(_legacy_module_status(_load_cfg()))


@legacy_api.route('/scan/status', methods=['GET'])
@require_auth
def legacy_scan_status():
    return jsonify(get_runtime_scan_status())


@legacy_api.route('/settings', methods=['GET'])
@require_auth
def legacy_settings_get():
    cfg = _load_cfg()
    hfish_config = cfg.get('hfish', {}).copy()
    hfish_config.pop('api_key', None)
    return jsonify({
        'hfish': hfish_config,
        'nmap': cfg.get('nmap', {}),
        'ai': _legacy_safe_ai(cfg),
        'logging': cfg.get('logging', {}),
        'status': _legacy_module_status(cfg),
    })


@legacy_api.route('/settings', methods=['POST'])
@require_auth
def legacy_settings_save():
    body = _body()
    cfg = _load_cfg()
    if 'hfish' in body:
        new_hfish = body['hfish']
        old_hfish = cfg.get('hfish', {})
        if not new_hfish.get('api_key') and old_hfish.get('api_key'):
            new_hfish['api_key'] = old_hfish['api_key']
        cfg['hfish'] = new_hfish
    if 'nmap' in body:
        cfg['nmap'] = body['nmap']
    if 'logging' in body:
        cfg['logging'] = body['logging']
    _save_cfg(cfg)
    return jsonify({'success': True, 'message': '设置已保存', 'status': _legacy_module_status(cfg)})


@legacy_api.route('/nmap/scans', methods=['GET'])
@require_auth
def legacy_nmap_scans():
    return ok(NmapModel.get_scans())


@legacy_api.route('/nmap/hosts', methods=['GET'])
@require_auth
def legacy_nmap_hosts():
    scan_id = request.args.get('scan_id')
    limit = _parse_int_arg('limit', 100)
    offset = _parse_int_arg('offset', 0)
    state = request.args.get('state')
    hosts = NmapModel.get_hosts(scan_id=int(scan_id) if scan_id else None, limit=limit, offset=offset, state=state)
    for h in hosts:
        _normalize_host_fields(h)
    return ok(hosts)


@legacy_api.route('/nmap/host/<ip>', methods=['GET'])
@require_auth
def legacy_nmap_host(ip: str):
    scan_id = request.args.get('scan_id')
    host = NmapModel.get_host_by_ip(ip, int(scan_id) if scan_id else None)
    return ok(_normalize_host_fields(host) or {})


@legacy_api.route('/nmap/vuln', methods=['GET'])
@require_auth
def legacy_nmap_vuln():
    limit = _parse_int_arg('limit', 1000)
    offset = _parse_int_arg('offset', 0)
    return ok(VulnModel.get_vuln_results(limit, offset))


@legacy_api.route('/nmap/vuln/stats', methods=['GET'])
@require_auth
def legacy_nmap_vuln_stats():
    return ok(VulnModel.get_vuln_stats())


@legacy_api.route('/nmap/vuln/mark_safe', methods=['POST'])
@require_auth
def legacy_nmap_mark_safe():
    body = _body()
    mac_address = body.get('mac_address')
    vuln_name = body.get('vuln_name')
    if not mac_address or not vuln_name:
        return jsonify({'success': False, 'message': '参数不全'})
    success = VulnModel.mark_safe(mac_address, vuln_name)
    if success:
        return jsonify({'success': True, 'message': '已手动标记为安全'})
    return jsonify({'success': False, 'message': '未找到对应记录'})


@legacy_api.route('/nmap/vuln/scan', methods=['POST'])
@require_auth
def legacy_nmap_vuln_scan():
    if _is_vuln_scanning:
        return jsonify({'success': False, 'message': '漏洞扫描正在进行中，请稍后再试'})

    _run_daemon(run_vuln_scan_task)
    return jsonify({'success': True, 'message': '漏洞扫描任务已启动'})


@legacy_api.route('/nmap/scan', methods=['POST'])
@require_auth
def legacy_nmap_scan():
    if _is_scanning:
        return jsonify({'success': False, 'message': '扫描正在进行中，请稍后再试'})

    body = _body()
    cfg = _load_cfg()
    ip_ranges = body.get('ip_ranges') or cfg.get('nmap', {}).get('ip_ranges', ['192.168.111.1/24'])
    arguments = body.get('arguments') or cfg.get('nmap', {}).get('arguments', '-sS -O -T4')
    if isinstance(ip_ranges, str):
        ip_ranges = [ip_ranges]

    _run_daemon(lambda: run_nmap_scan(ip_ranges, arguments))
    return jsonify({'success': True, 'message': '扫描任务已启动', 'ip_ranges': ip_ranges})
