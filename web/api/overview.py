"""
Overview Module - Dashboard and metrics endpoints
"""
from flask import Blueprint, request
from database.models import NmapModel, VulnModel, HFishModel, AiModel
from database.db import get_connection
from .helpers import require_auth, ok, _load_cfg

overview_bp = Blueprint('overview', __name__, url_prefix='/api/v1/overview')


@overview_bp.route('/metrics', methods=['GET'])
@require_auth
def overview_metrics():
    """Dashboard metrics"""
    hfish = HFishModel.get_stats()
    nmap_stats = NmapModel.get_stats()
    vuln = VulnModel.get_vuln_stats()

    online = next((s['count'] for s in nmap_stats.get('state_stats', []) if s['state'] == 'up'), 0)
    ai_analyses = AiModel.get_all_analyses()
    blocked = sum(1 for a in ai_analyses.values() if a.get('decision') == 'true')

    return ok({
        'hfish_total': hfish.get('total', 0),
        'nmap_online': online,
        'vuln_open': vuln.get('vulnerable', 0),
        'ai_decisions': len(ai_analyses),
        'blocked_ips': blocked,
    })


@overview_bp.route('/chain-status', methods=['GET'])
@require_auth
def overview_chain_status():
    """Module status"""
    cfg = _load_cfg()
    ai_enabled = cfg.get('ai', {}).get('enabled', False)
    auto_ban = cfg.get('ai', {}).get('auto_ban', False)
    switches = cfg.get('switches', [])
    active_switches = [sw for sw in switches if isinstance(sw, dict) and sw.get('host') and sw.get('enabled', True)]

    return ok({
        'hfish_sync': cfg.get('hfish', {}).get('sync_enabled', False),
        'nmap_scan': cfg.get('nmap', {}).get('scan_enabled', False),
        'ai_analysis': ai_enabled,
        'acl_auto_ban': bool(ai_enabled and auto_ban and active_switches),
    })


@overview_bp.route('/screen', methods=['GET'])
@require_auth
def overview_screen():
    """Big-screen aggregated payload for dashboard"""
    hfish = HFishModel.get_stats()
    nmap_stats = NmapModel.get_stats()
    vuln = VulnModel.get_vuln_stats()
    ai_analyses = AiModel.get_all_analyses()
    cfg = _load_cfg()

    online = next((s['count'] for s in nmap_stats.get('state_stats', []) if s['state'] == 'up'), 0)
    blocked = sum(1 for a in ai_analyses.values() if a.get('decision') == 'true')

    switches = cfg.get('switches', []) if isinstance(cfg.get('switches', []), list) else []
    active_switches = [sw for sw in switches if isinstance(sw, dict) and sw.get('host') and sw.get('enabled', True)]

    # 最近攻击与防御事件（轻量聚合，避免前端多请求拼装）
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT attack_ip, ip_location, service_name, create_time_str
        FROM attack_logs
        ORDER BY create_time_timestamp DESC
        LIMIT 10
    """)
    recent_attacks = []
    for r in c.fetchall():
        row = dict(r)
        recent_attacks.append({
            'attack_ip': row.get('attack_ip') or '-',
            'ip_location': row.get('ip_location') or '未知地区',
            'service_name': row.get('service_name') or '未知服务',
            'create_time_str': row.get('create_time_str') or '-',
        })

    c.execute("""
        SELECT
            l.attack_ip,
            MAX(l.ip_location) as ip_location,
            COUNT(*) as attack_count,
            MAX(l.create_time_str) as latest_time,
            a.status as ai_status,
            a.decision as ai_decision
        FROM attack_logs l
        LEFT JOIN ai_analysis_logs a ON l.attack_ip = a.ip
        GROUP BY l.attack_ip
        ORDER BY attack_count DESC
        LIMIT 8
    """)
    defense_events = []
    for r in c.fetchall():
        row = dict(r)
        defense_events.append({
            'attack_ip': row.get('attack_ip') or '-',
            'ip_location': row.get('ip_location') or '未知地区',
            'attack_count': row.get('attack_count') or 0,
            'latest_time': row.get('latest_time') or '-',
            'ai_status': row.get('ai_status') or 'pending',
            'ai_decision': row.get('ai_decision') if row.get('ai_decision') is not None else 'pending',
        })
    conn.close()

    hosts = NmapModel.get_hosts(limit=10, offset=0)
    lan_hosts = []
    for h in hosts:
        open_ports = h.get('open_ports') or ''
        if isinstance(open_ports, str):
            ports = [p.strip() for p in open_ports.split(',') if p.strip()]
        elif isinstance(open_ports, list):
            ports = [str(p) for p in open_ports if str(p).strip()]
        else:
            ports = []
        lan_hosts.append({
            'ip': h.get('ip') or '-',
            'hostname': h.get('hostname') or '-',
            'state': h.get('state') or 'unknown',
            'os_type': h.get('os_type') or '-',
            'open_ports': ports,
        })

    topology_nodes = [
        {'id': 'internet', 'label': '互联网', 'type': 'edge', 'status': 'online'},
        {'id': 'firewall', 'label': '主防火墙', 'type': 'firewall', 'status': 'online'},
    ]
    topology_links = [
        {'source': 'internet', 'target': 'firewall', 'type': 'uplink'},
    ]
    for idx, sw in enumerate(active_switches):
        sid = f"switch-{idx + 1}"
        topology_nodes.append({
            'id': sid,
            'label': sw.get('host', f'交换机{idx + 1}'),
            'type': 'switch',
            'status': 'online' if sw.get('enabled', True) else 'offline',
        })
        topology_links.append({'source': 'firewall', 'target': sid, 'type': 'lan'})

    payload = {
        'top_metrics': {
            'hfish_total': hfish.get('total', 0),
            'nmap_online': online,
            'vuln_open': vuln.get('vulnerable', 0),
            'ai_decisions': len(ai_analyses),
            'blocked_ips': blocked,
        },
        'chain_status': {
            'hfish_sync': cfg.get('hfish', {}).get('sync_enabled', False),
            'nmap_scan': cfg.get('nmap', {}).get('scan_enabled', False),
            'ai_analysis': cfg.get('ai', {}).get('enabled', False),
            'acl_auto_ban': bool(cfg.get('ai', {}).get('enabled', False) and cfg.get('ai', {}).get('auto_ban', False) and active_switches),
        },
        'trends': {
            'labels': [x.get('date') for x in hfish.get('time_stats', [])],
            'counts': [x.get('count', 0) for x in hfish.get('time_stats', [])],
        },
        'hot_services': hfish.get('service_stats', []),
        'recent_attacks': recent_attacks,
        'defense_events': defense_events,
        'topology': {
            'nodes': topology_nodes,
            'links': topology_links,
        },
        'lan_hosts': lan_hosts,
        'switches': [
            {
                'host': sw.get('host'),
                'port': sw.get('port', 23),
                'acl_number': sw.get('acl_number', 30),
                'enabled': sw.get('enabled', True),
            }
            for sw in active_switches
        ],
    }
    return ok(payload)
