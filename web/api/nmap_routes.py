"""
Nmap Routes Module - Nmap endpoints under /api/v1/ namespace
"""
from flask import Blueprint, request, jsonify
from database.models import NmapModel
from .helpers import require_auth, ok, _parse_int_arg, _normalize_host_fields, _load_cfg

nmap_bp = Blueprint('nmap', __name__, url_prefix='/api/nmap')


@nmap_bp.route('/scans', methods=['GET'])
@require_auth
def v1_nmap_scans():
    """Get nmap scans"""
    return ok(NmapModel.get_scans())


@nmap_bp.route('/scan', methods=['POST'])
@require_auth
def v1_nmap_scan():
    """Trigger a manual nmap/fscan scan"""
    from .runtime import get_runtime_scan_status, run_nmap_scan, _is_scanning, _run_daemon

    if _is_scanning:
        return jsonify({'success': False, 'message': '扫描正在进行中，请稍后再试'})

    body = request.get_json() or {}
    cfg = _load_cfg()
    ip_ranges = body.get('ip_ranges') or cfg.get('nmap', {}).get('ip_ranges', ['192.168.111.1/24'])
    arguments = body.get('arguments') or cfg.get('nmap', {}).get('arguments', '-sS -O -T5')
    if isinstance(ip_ranges, str):
        ip_ranges = [ip_ranges]

    _run_daemon(lambda: run_nmap_scan(ip_ranges, arguments))
    return jsonify({'success': True, 'message': '扫描任务已启动', 'ip_ranges': ip_ranges})


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


@nmap_bp.route('/screenshots/<ip>', methods=['GET'])
@require_auth
def v1_nmap_screenshots(ip: str):
    """Get all screenshots for an IP"""
    from database.models import ScreenshotModel
    screenshots = ScreenshotModel.get_screenshot(ip)
    return ok(screenshots)


@nmap_bp.route('/screenshots/<ip>/<int:port>', methods=['GET'])
@require_auth
def v1_nmap_screenshot_by_port(ip: str, port: int):
    """Get screenshot for specific IP:port"""
    from database.models import ScreenshotModel
    screenshots = ScreenshotModel.get_screenshot(ip, port)
    if not screenshots:
        return ok(None)
    return ok(screenshots[0])


@nmap_bp.route('/screenshots/all', methods=['GET'])
@require_auth
def v1_nmap_all_screenshots():
    """Get all screenshots across all hosts"""
    from database.models import ScreenshotModel
    limit = _parse_int_arg('limit', 200)
    screenshots = ScreenshotModel.get_all_screenshots(limit=limit)
    return ok(screenshots)


@nmap_bp.route('/screenshot/<ip>/<int:port>', methods=['GET'])
@require_auth
def v1_nmap_screenshot_image(ip: str, port: int):
    """Serve screenshot image file for specific IP:port"""
    import os
    from flask import send_file, abort

    # 先从数据库获取路径
    from database.models import ScreenshotModel
    screenshots = ScreenshotModel.get_screenshot(ip, port)
    if screenshots:
        screenshot_path = screenshots[0].get('screenshot_path')
        if screenshot_path and os.path.exists(screenshot_path):
            return send_file(screenshot_path, mimetype='image/png')

    # 文件不存在，返回 404
    return abort(404)


@nmap_bp.route('/screenshot', methods=['POST'])
@require_auth
def v1_nmap_take_screenshot():
    """Directly take a screenshot of a web page"""
    from flask import jsonify
    from plugin.web_screenshot import take_screenshot
    from database.models import ScreenshotModel
    from datetime import datetime

    data = request.get_json() or {}
    url = data.get('url')
    ip = data.get('ip')
    port = data.get('port')
    scan_id = data.get('scan_id')

    if not url or not ip or not port:
        return jsonify({'ok': False, 'error': '缺少 url、ip 或 port 参数'}), 400

    try:
        port = int(port)
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'port 必须是整数'}), 400

    path = take_screenshot(url, ip, port)
    if path:
        scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ScreenshotModel.save_screenshot(ip, port, url, path, scan_time, scan_id)
        return jsonify({
            'ok': True,
            'ip': ip,
            'port': port,
            'url': url,
            'scan_id': scan_id,
            'screenshot_path': path,
            'screenshot_url': f'/api/nmap/screenshot/{ip}/{port}',
        })
    else:
        return jsonify({'ok': False, 'error': '截图失败'}), 500

