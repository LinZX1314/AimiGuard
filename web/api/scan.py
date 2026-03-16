"""
Scan Module - Nmap and vulnerability scan endpoints
"""
from flask import Blueprint, request
from database.models import VulnModel
from database.db import get_connection
from .helpers import require_auth, ok, _parse_int_arg

scan_bp = Blueprint('scan', __name__, url_prefix='/api/v1/scan')


@scan_bp.route('/findings', methods=['GET'])
@require_auth
def scan_findings():
    """Get vulnerability findings with pagination"""
    page = _parse_int_arg('page', 1)
    page_size = _parse_int_arg('page_size', 50)
    severity = request.args.get('severity')
    status = request.args.get('status')
    offset = (page - 1) * page_size

    conn = get_connection()
    c = conn.cursor()

    # Build query with filters
    where_clauses = []
    params = []
    if severity:
        SEV_MAP = {'严重': 'vulnerable', '高危': 'vulnerable', '中危': 'error', '低危': 'safe', '信息': 'safe'}
        # Simplified mapping - adjust as needed
        where_clauses.append('vuln_result = ?')
        params.append(severity)

    where_sql = ' AND '.join(where_clauses) if where_clauses else '1=1'

    # Get total count
    count_q = f"SELECT COUNT(*) as total FROM vuln_scan_results WHERE {where_sql}"
    c.execute(count_q, params)
    total = c.fetchone()['total']

    # Get paginated results
    q = f"SELECT * FROM vuln_scan_results WHERE {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([page_size, offset])
    c.execute(q, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    SEV = {'vulnerable': '高危', 'error': '中危', 'safe': '低危'}
    STA = {'vulnerable': 'open', 'safe': 'fixed', 'error': 'open'}
    findings = [{
        'id': r.get('id', 0),
        'vuln_name': r.get('vuln_name', '未知漏洞'),
        'ip': r.get('ip', r.get('mac_address', '')),
        'port': None,
        'severity': SEV.get(r.get('vuln_result', ''), '信息'),
        'status': STA.get(r.get('vuln_result', ''), 'open'),
        'os_tags': r.get('os_tags', ''),
        'detail': r.get('vuln_details', ''),
        'created_at': r.get('scan_time', ''),
    } for r in rows]
    return ok({'items': findings, 'total': total, 'page': page, 'page_size': page_size})


@scan_bp.route('/findings/<int:finding_id>/status', methods=['PUT'])
@require_auth
def scan_finding_status(finding_id: int):
    """Update finding status"""
    return ok()
