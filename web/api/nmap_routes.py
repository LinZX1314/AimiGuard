"""
Nmap Routes Module - Nmap endpoints under /api/v1/ namespace
"""
from flask import Blueprint, request
from database.models import NmapModel
from .helpers import require_auth, ok, _parse_int_arg, _normalize_host_fields

nmap_bp = Blueprint('nmap', __name__, url_prefix='/api/nmap')


@nmap_bp.route('/scans', methods=['GET'])
@require_auth
def v1_nmap_scans():
    """Get nmap scans"""
    return ok(NmapModel.get_scans())


@nmap_bp.route('/scans/clear', methods=['POST'])
@require_auth
def v1_nmap_scans_clear():
    """Clear nmap scan history"""
    NmapModel.clear_scan_history()
    return ok({'cleared': True})


@nmap_bp.route('/hosts', methods=['GET'])
@require_auth
def v1_nmap_hosts():
    """Get nmap hosts with pagination"""
    page = _parse_int_arg('page', 1)
    page_size = _parse_int_arg('page_size', 50)
    scan_id = request.args.get('scan_id')
    offset = (page - 1) * page_size

    # Get total count
    from database.db import get_connection
    conn = get_connection()
    c = conn.cursor()
    if scan_id:
        c.execute("SELECT COUNT(*) as total FROM hosts WHERE scan_id = ?", (scan_id,))
    else:
        c.execute("SELECT COUNT(*) as total FROM hosts")
    total = c.fetchone()['total']
    conn.close()

    hosts = NmapModel.get_hosts(scan_id=int(scan_id) if scan_id else None, limit=page_size, offset=offset)
    for h in hosts:
        _normalize_host_fields(h)
    return ok({'items': hosts, 'total': total, 'page': page, 'page_size': page_size})


@nmap_bp.route('/host/<ip>', methods=['GET'])
@require_auth
def v1_nmap_host(ip: str):
    """Get host by IP"""
    scan_id_raw = request.args.get('scan_id')
    scan_id = int(scan_id_raw) if scan_id_raw and str(scan_id_raw).isdigit() else None
    h = NmapModel.get_host_by_ip(ip, scan_id=scan_id)
    return ok(_normalize_host_fields(h))
