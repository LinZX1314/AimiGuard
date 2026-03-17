"""
Settings Module - General settings endpoints
"""
from flask import Blueprint
from .helpers import (
    require_auth, ok, _body, _load_cfg, _save_cfg, _as_bool
)

settings_bp = Blueprint('settings', __name__, url_prefix='')


@settings_bp.route('/settings', methods=['GET'])
@require_auth
def settings_get():
    """Get settings"""
    cfg = _load_cfg()
    
    # 确保每个交换机都有enabled字段
    switches = cfg.get('switches', [])
    for sw in switches:
        if isinstance(sw, dict):
            sw.setdefault('enabled', True)
    
    return ok({
        'hfish': {
            'host_port': cfg.get('hfish', {}).get('host_port', ''),
            'api_base_url': cfg.get('hfish', {}).get('api_base_url', ''),
            'sync_interval': cfg.get('hfish', {}).get('sync_interval', 60),
            'sync_enabled': cfg.get('hfish', {}).get('sync_enabled', False),
        },
        'nmap': {
            'ip_ranges': cfg.get('nmap', {}).get('ip_ranges', []),
            'arguments': cfg.get('nmap', {}).get('arguments', '-sS -O -T5'),
            'scan_interval': cfg.get('nmap', {}).get('scan_interval', 604800),
            'scan_enabled': cfg.get('nmap', {}).get('scan_enabled', False),
            'vuln_scripts_by_tag': cfg.get('nmap', {}).get('vuln_scripts_by_tag', {}),
        },
        'switches': switches,
        'switch_status': {
            'strict_mode': cfg.get('switch_status', {}).get('strict_mode', False),
        },
        'logging': cfg.get('logging', {}),
    })


@settings_bp.route('/settings', methods=['POST'])
@require_auth
def settings_save():
    """Save settings"""
    body = _body()
    cfg = _load_cfg()

    if 'hfish' in body:
        h = body['hfish']
        sync_enabled = h.get('sync_enabled', h.get('enabled', cfg.get('hfish', {}).get('sync_enabled', False)))
        cfg.setdefault('hfish', {}).update({
            'host_port': h.get('host_port', cfg.get('hfish', {}).get('host_port', '')),
            'sync_interval': int(h.get('sync_interval', 60)),
            'sync_enabled': _as_bool(sync_enabled),
        })
        if 'api_base_url' in h:
            cfg['hfish']['api_base_url'] = h.get('api_base_url', '')
        if h.get('api_key'):
            cfg['hfish']['api_key'] = h['api_key']

    if 'nmap' in body:
        n = body['nmap']
        ranges = n.get('ip_ranges', [])
        if isinstance(ranges, str):
            ranges = [r.strip() for r in ranges.split(',') if r.strip()]
        cfg.setdefault('nmap', {}).update({
            'ip_ranges': ranges,
            'arguments': n.get('arguments', '-sS -O -T5'),
            'scan_interval': int(n.get('scan_interval', 604800)),
            'scan_enabled': _as_bool(n.get('scan_enabled', False)),
            'vuln_scripts_by_tag': n.get('vuln_scripts_by_tag', {}),
        })

    if 'switches' in body:
        switches = body['switches']
        if isinstance(switches, list):
            # 验证并清理交换机配置
            cleaned = []
            for sw in switches:
                if isinstance(sw, dict) and sw.get('host'):
                    cleaned.append({
                        'host': str(sw.get('host', '')).strip(),
                        'port': int(sw.get('port', 23)),
                        'password': str(sw.get('password', '')).strip(),
                        'acl_number': int(sw.get('acl_number', 30)),
                        'enabled': _as_bool(sw.get('enabled', True)),
                    })
            cfg['switches'] = cleaned

    if 'switch_status' in body:
        ss = body['switch_status'] or {}
        cfg.setdefault('switch_status', {}).update({
            'strict_mode': _as_bool(ss.get('strict_mode', cfg.get('switch_status', {}).get('strict_mode', False))),
        })

    if 'logging' in body:
        cfg['logging'] = {**cfg.get('logging', {}), **body['logging']}

    _save_cfg(cfg)
    return ok()
