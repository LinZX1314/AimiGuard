"""
Scan Module - Nmap and vulnerability scan endpoints
"""
from flask import Blueprint
from database.models import VulnModel
from .helpers import require_auth, ok, _parse_int_arg

scan_bp = Blueprint('scan', __name__, url_prefix='/scan')


@scan_bp.route('/findings', methods=['GET'])
@require_auth
def scan_findings():
    """Get vulnerability findings"""
    limit = _parse_int_arg('limit', 500)
    vulns = VulnModel.get_vuln_results(limit=limit)
    SEV = {'vulnerable': '高危', 'error': '中危', 'safe': '低危'}
    STA = {'vulnerable': 'open', 'safe': 'fixed', 'error': 'open'}
    findings = [{
        'id': i + 1,
        'vuln_name': v.get('vuln_name', '未知漏洞'),
        'ip': v.get('ip', v.get('mac_address', '')),
        'port': None,
        'severity': SEV.get(v.get('vuln_result', ''), '信息'),
        'status': STA.get(v.get('vuln_result', ''), 'open'),
        'os_tags': v.get('os_tags', ''),
        'detail': v.get('vuln_details', ''),
        'created_at': v.get('scan_time', ''),
    } for i, v in enumerate(vulns)]
    return ok({'items': findings, 'total': len(findings)})


@scan_bp.route('/findings/<int:finding_id>/status', methods=['PUT'])
@require_auth
def scan_finding_status(finding_id: int):
    """Update finding status"""
    return ok()
