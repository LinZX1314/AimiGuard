"""
Legacy API Module - Old API compatibility layer
"""
from flask import Blueprint, request, jsonify
from database.models import NmapModel
from .helpers import (
    require_auth, ok, err, _body, _load_cfg, _save_cfg,
    _parse_int_arg, _normalize_host_fields
)
from .runtime import (
    get_runtime_scan_status, run_nmap_scan,
    _is_scanning, _run_daemon
)

legacy_bp = Blueprint('legacy_api', __name__, url_prefix='/api')


def _legacy_module_status(cfg: dict) -> dict:
    ai_cfg = cfg.get('ai', {})
    ai_enabled = ai_cfg.get('enabled', False)
    auto_ban = ai_cfg.get('auto_ban', False)
    switches = cfg.get('switches', [])
    active_switches = [sw for sw in switches if isinstance(sw, dict) and sw.get('host') and sw.get('enabled', True)]
    return {
        'hfish_sync': cfg.get('hfish', {}).get('sync_enabled', False),
        'nmap_scan': cfg.get('nmap', {}).get('scan_enabled', False),
        'ai_analysis': ai_enabled,
        'acl_auto_ban': bool(ai_enabled and auto_ban and active_switches),
    }


def _legacy_safe_ai(cfg: dict) -> dict:
    ai = cfg.get('ai', {}).copy()
    ai.pop('api_key', None)
    return ai


@legacy_bp.route('/status', methods=['GET'])
@require_auth
def legacy_status():
    return jsonify(_legacy_module_status(_load_cfg()))


@legacy_bp.route('/scan/status', methods=['GET'])
@require_auth
def legacy_scan_status():
    return jsonify(get_runtime_scan_status())


@legacy_bp.route('/settings', methods=['GET'])
@require_auth
def legacy_settings_get():
    cfg = _load_cfg()
    hfish_config = cfg.get('hfish', {}).copy()
    hfish_config.pop('api_key', None)
    switches = cfg.get('switches', [])
    # 兼容旧前端：确保每个交换机都带 enabled 字段
    for sw in switches:
        if isinstance(sw, dict):
            sw.setdefault('enabled', True)

    return jsonify({
        'hfish': hfish_config,
        'nmap': cfg.get('nmap', {}),
        'ai': _legacy_safe_ai(cfg),
        'switches': switches,
        'logging': cfg.get('logging', {}),
        'status': _legacy_module_status(cfg),
    })


@legacy_bp.route('/settings', methods=['POST'])
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


@legacy_bp.route('/system/config', methods=['GET'])
@require_auth
def legacy_system_config_get():
    cfg = _load_cfg()
    hfish = cfg.get('hfish', {})
    switches = cfg.get('switches', [])
    first_switch = switches[0] if switches else {}
    return ok({
        'hfish_url': hfish.get('api_base_url', '') or hfish.get('host_port', ''),
        'hfish_token': hfish.get('api_key', ''),
        'switch_ip': first_switch.get('host', ''),
        'switch_username': first_switch.get('username', ''),
        'switch_password': first_switch.get('password', ''),
        'ai_enabled': cfg.get('ai', {}).get('enabled', False),
        'ai_url': cfg.get('ai', {}).get('api_url', ''),
        'ai_model': cfg.get('ai', {}).get('model', ''),
    })


@legacy_bp.route('/system/config', methods=['POST'])
@require_auth
def legacy_system_config_save():
    body = _body()
    cfg = _load_cfg()

    hfish = cfg.setdefault('hfish', {})
    if 'hfish_url' in body:
        hfish_url = str(body.get('hfish_url', '')).strip()
        hfish['api_base_url'] = hfish_url
        if hfish_url and hfish_url.startswith('http'):
            from urllib.parse import urlparse
            parsed = urlparse(hfish_url)
            if parsed.netloc:
                hfish['host_port'] = parsed.netloc
    if 'hfish_token' in body:
        hfish_token = str(body.get('hfish_token', '')).strip()
        if hfish_token:
            hfish['api_key'] = hfish_token

    switches = cfg.setdefault('switches', [])
    if not switches:
        switches.append({})
    switch = switches[0]
    if 'switch_ip' in body:
        switch['host'] = str(body.get('switch_ip', '')).strip()
    if 'switch_username' in body:
        switch['username'] = str(body.get('switch_username', '')).strip()
    if 'switch_password' in body:
        switch['password'] = str(body.get('switch_password', '')).strip()

    ai = cfg.setdefault('ai', {})
    if 'ai_enabled' in body:
        ai['enabled'] = _as_bool(body.get('ai_enabled', False))
    if 'ai_url' in body:
        ai['api_url'] = str(body.get('ai_url', '')).strip()
    if 'ai_model' in body:
        ai['model'] = str(body.get('ai_model', '')).strip()

    _save_cfg(cfg)
    return ok({'success': True})


@legacy_bp.route('/nmap/scans', methods=['GET'])
@require_auth
def legacy_nmap_scans():
    return ok(NmapModel.get_scans())


@legacy_bp.route('/nmap/hosts', methods=['GET'])
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


@legacy_bp.route('/nmap/host/<ip>', methods=['GET'])
@require_auth
def legacy_nmap_host(ip: str):
    scan_id = request.args.get('scan_id')
    host = NmapModel.get_host_by_ip(ip, int(scan_id) if scan_id else None)
    return ok(_normalize_host_fields(host) or {})


@legacy_bp.route('/nmap/scan', methods=['POST'])
@require_auth
def legacy_nmap_scan():
    if _is_scanning:
        return jsonify({'success': False, 'message': '扫描正在进行中，请稍后再试'})

    body = _body()
    cfg = _load_cfg()
    ip_ranges = body.get('ip_ranges') or cfg.get('nmap', {}).get('ip_ranges', ['192.168.111.1/24'])
    arguments = body.get('arguments') or cfg.get('nmap', {}).get('arguments', '-sS -O -T5')
    if isinstance(ip_ranges, str):
        ip_ranges = [ip_ranges]

    _run_daemon(lambda: run_nmap_scan(ip_ranges, arguments))
    return jsonify({'success': True, 'message': '扫描任务已启动', 'ip_ranges': ip_ranges})
