"""
Nmap Routes Module - Nmap endpoints under /api/v1/ namespace
"""
from flask import Blueprint, request
from database.models import NmapModel
from .helpers import require_auth, ok, _parse_int_arg, _normalize_host_fields

nmap_bp = Blueprint('nmap', __name__, url_prefix='/nmap')


@nmap_bp.route('/scans', methods=['GET'])
@require_auth
def v1_nmap_scans():
    """Get nmap scans"""
    return ok(NmapModel.get_scans())


@nmap_bp.route('/hosts', methods=['GET'])
@require_auth
def v1_nmap_hosts():
    """Get nmap hosts"""
    limit = _parse_int_arg('limit', 500)
    scan_id = request.args.get('scan_id')
    hosts = NmapModel.get_hosts(scan_id=int(scan_id) if scan_id else None, limit=limit)
    for h in hosts:
        _normalize_host_fields(h)
    return ok(hosts)


@nmap_bp.route('/host/<ip>', methods=['GET'])
@require_auth
def v1_nmap_host(ip: str):
    """Get host by IP"""
    h = NmapModel.get_host_by_ip(ip)
    return ok(_normalize_host_fields(h))
