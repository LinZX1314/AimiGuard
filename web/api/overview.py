"""
Overview Module - Dashboard and metrics endpoints
"""
from flask import Blueprint, request
from database.models import NmapModel, VulnModel, HFishModel, AiModel
from .helpers import require_auth, ok, _load_cfg

overview_bp = Blueprint('overview', __name__, url_prefix='/api/v1/overview')


@overview_bp.route('/metrics', methods=['GET'])
@require_auth
def overview_metrics():
    """Dashboard metrics"""
    hfish = HFishModel.get_stats()
    nmap_stats = NmapModel.get_stats()
    vuln = VulnModel.get_vuln_stats()

    high_count = next((s['count'] for s in hfish.get('threat_stats', []) if s['level'] in ('高危', 'HIGH')), 0)
    online = next((s['count'] for s in nmap_stats.get('state_stats', []) if s['state'] == 'up'), 0)
    ai_analyses = AiModel.get_all_analyses()
    blocked = sum(1 for a in ai_analyses.values() if a.get('decision') == 'true')

    return ok({
        'hfish_total': hfish.get('total', 0),
        'hfish_high': high_count,
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
