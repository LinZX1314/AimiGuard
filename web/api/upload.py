from flask import Blueprint, request, jsonify
import os
import datetime
import re
import json

upload_bp = Blueprint('upload', __name__)
TERMINAL_COUNTER_SERVICE_NAME = '反制蜜罐·终端取证'

# 配置上传根目录（web/public/uploads）
UPLOAD_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'vue', 'public', 'uploads')
SCREENSHOT_DIR = os.path.join(UPLOAD_ROOT, 'screenshots')
CAMERA_DIR = os.path.join(UPLOAD_ROOT, 'camera')
TERMINAL_META_DIR = os.path.join(UPLOAD_ROOT, 'terminal_meta')

# 确保目录存在
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(CAMERA_DIR, exist_ok=True)
os.makedirs(TERMINAL_META_DIR, exist_ok=True)


_EVENT_KEY_RE = re.compile(r'^(?:screenshot|camera)_(\d{8}_\d{6})$')
_EVENT_TIME_RE = re.compile(r'^\d{8}_\d{6}$')


def _extract_event_key(filename: str) -> str:
    stem = os.path.splitext(filename)[0]
    matched = _EVENT_KEY_RE.match(stem)
    if matched:
        return matched.group(1)
    return stem


def _format_event_time(event_key: str, mtime: float) -> str:
    try:
        if re.fullmatch(r'\d{8}_\d{6}', event_key):
            dt = datetime.datetime.strptime(event_key, "%Y%m%d_%H%M%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")


def _capture_summary(capture_types: list[str]) -> str:
    has_screenshot = 'screenshot' in capture_types
    has_camera = 'camera' in capture_types
    if has_screenshot and has_camera:
        return '截图+摄像头'
    if has_camera:
        return '摄像头'
    return '截图'


def _normalize_event_key(raw_event_key: str | None, fallback: str) -> str:
    value = (raw_event_key or '').strip()
    if _EVENT_TIME_RE.fullmatch(value):
        return value
    return fallback


def _meta_file_path(event_key: str) -> str:
    return os.path.join(TERMINAL_META_DIR, f"{event_key}.json")


def _read_event_meta(event_key: str) -> dict:
    path = _meta_file_path(event_key)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_event_meta(event_key: str, capture_type: str, payload: dict):
    meta = _read_event_meta(event_key)
    channels = meta.get('channels')
    if not isinstance(channels, dict):
        channels = {}

    channel_meta = channels.get(capture_type)
    if not isinstance(channel_meta, dict):
        channel_meta = {}

    channel_meta.update({
        'filename': payload.get('filename') or '',
        'url': payload.get('url') or '',
        'upload_api': payload.get('upload_api') or '',
        'client_time': payload.get('client_time') or '',
        'server_time': payload.get('server_time') or '',
    })
    channels[capture_type] = channel_meta

    meta.update({
        'event_key': event_key,
        'client_info': payload.get('client_info') or meta.get('client_info') or '',
        'client_name': payload.get('client_name') or meta.get('client_name') or '',
        'client_host': payload.get('client_host') or meta.get('client_host') or '',
        'client_ip': payload.get('client_ip') or meta.get('client_ip') or '',
        'client_time': payload.get('client_time') or meta.get('client_time') or '',
        'upload_api': payload.get('upload_api') or meta.get('upload_api') or '',
        'channels': channels,
        'last_server_time': payload.get('server_time') or meta.get('last_server_time') or '',
    })

    path = _meta_file_path(event_key)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def collect_terminal_evidence_events(limit: int | None = None):
    """读取终端上传目录并按事件聚合取证列表（截图+摄像头记为一次攻击）。"""
    events: dict[str, dict] = {}

    def add_capture(item_type: str, filename: str, file_url: str, mtime: float):
        event_key = _extract_event_key(filename)
        item = events.get(event_key)
        if item is None:
            item = {
                'event_key': event_key,
                'source': 'terminal',
                'severity': 'high',
                'severity_label': '高危回传',
                'attack_kind': 'counter_honeypot',
                'attack_source': '终端取证节点',
                'service_name': TERMINAL_COUNTER_SERVICE_NAME,
                'capture_types': set(),
                'screenshot_filename': '',
                'screenshot_url': '',
                'camera_filename': '',
                'camera_url': '',
                'mtime': mtime,
            }
            events[event_key] = item

        item['capture_types'].add(item_type)
        item['mtime'] = max(item['mtime'], mtime)

        if item_type == 'camera':
            item['camera_filename'] = filename
            item['camera_url'] = file_url
        else:
            item['screenshot_filename'] = filename
            item['screenshot_url'] = file_url

    if os.path.exists(SCREENSHOT_DIR):
        for filename in os.listdir(SCREENSHOT_DIR):
            if filename.endswith((".png", ".jpg", ".jpeg")):
                file_path = os.path.join(SCREENSHOT_DIR, filename)
                add_capture(
                    item_type='screenshot',
                    filename=filename,
                    file_url=f"/uploads/screenshots/{filename}",
                    mtime=os.path.getmtime(file_path),
                )

    if os.path.exists(CAMERA_DIR):
        for filename in os.listdir(CAMERA_DIR):
            if filename.endswith((".png", ".jpg", ".jpeg")):
                file_path = os.path.join(CAMERA_DIR, filename)
                add_capture(
                    item_type='camera',
                    filename=filename,
                    file_url=f"/uploads/camera/{filename}",
                    mtime=os.path.getmtime(file_path),
                )

    results = []
    for item in events.values():
        meta = _read_event_meta(item['event_key'])
        channels = meta.get('channels') if isinstance(meta.get('channels'), dict) else {}
        screenshot_meta = channels.get('screenshot') if isinstance(channels.get('screenshot'), dict) else {}
        camera_meta = channels.get('camera') if isinstance(channels.get('camera'), dict) else {}

        capture_types = sorted(list(item['capture_types']), key=lambda x: 0 if x == 'screenshot' else 1)
        summary = _capture_summary(capture_types)
        preview_url = item['screenshot_url'] or item['camera_url']
        event_time = _format_event_time(item['event_key'], item['mtime'])

        screenshot_api = screenshot_meta.get('upload_api') or ''
        camera_api = camera_meta.get('upload_api') or ''
        upload_api = meta.get('upload_api') or screenshot_api or camera_api
        if screenshot_api and camera_api and screenshot_api != camera_api:
            upload_api = f"{screenshot_api} | {camera_api}"

        client_time = (
            meta.get('client_time')
            or screenshot_meta.get('client_time')
            or camera_meta.get('client_time')
            or event_time
        )

        results.append({
            'event_key': item['event_key'],
            'source': item['source'],
            'severity': item['severity'],
            'severity_label': item['severity_label'],
            'attack_kind': item['attack_kind'],
            'service_name': item['service_name'],
            'attack_source': item['attack_source'],
            'capture_types': capture_types,
            'capture_summary': summary,
            'is_combined': len(capture_types) > 1,
            'preview_url': preview_url,
            'time': event_time,
            'mtime': item['mtime'],
            'filename': item['screenshot_filename'] or item['camera_filename'] or item['event_key'],
            'url': preview_url,
            'screenshot_filename': item['screenshot_filename'],
            'screenshot_url': item['screenshot_url'],
            'camera_filename': item['camera_filename'],
            'camera_url': item['camera_url'],
            'jump_path': '/screenshots',
            'attack_count': 1,
            'upload_api': upload_api,
            'client_time': client_time,
            'client_name': meta.get('client_name') or '终端取证客户端',
            'client_host': meta.get('client_host') or '',
            'client_ip': meta.get('client_ip') or '',
            'client_info': meta.get('client_info') or '',
            'screenshot_api': screenshot_api,
            'camera_api': camera_api,
        })

    results.sort(key=lambda item: item['mtime'], reverse=True)
    if isinstance(limit, int) and limit > 0:
        return results[:limit]
    return results


def collect_terminal_evidence(limit: int | None = None):
    """兼容旧调用：返回聚合后的终端取证事件列表。"""
    return collect_terminal_evidence_events(limit=limit)

@upload_bp.route('/api/upload/screenshot', methods=['POST'])
def upload_screenshot():
    if 'file' not in request.files:
        return jsonify({"error": "没有文件"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "文件名为空"}), 400

    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    event_key = _normalize_event_key(request.form.get('event_key'), timestamp)

    client_info = request.form.get('info', 'client_upload')
    client_name = (request.form.get('client_name', '终端取证客户端') or '终端取证客户端').strip()
    client_host = request.form.get('client_host', '').strip()
    client_ip = request.form.get('client_ip', '').strip()
    client_time = request.form.get('client_time', '').strip()
    upload_api = (request.form.get('upload_api', request.path) or request.path).strip()

    filename = f"screenshot_{event_key}.png"
    filepath = os.path.join(SCREENSHOT_DIR, filename)

    file.save(filepath)

    relative_url = f"/uploads/screenshots/{filename}"
    server_time = now.strftime("%Y-%m-%d %H:%M:%S")
    _write_event_meta(event_key, 'screenshot', {
        'filename': filename,
        'url': relative_url,
        'upload_api': upload_api,
        'client_time': client_time,
        'client_name': client_name,
        'client_host': client_host,
        'client_ip': client_ip,
        'client_info': client_info,
        'server_time': server_time,
    })
    
    # 记录到系统日志
    from web.flask_app import append_log
    append_log("info", f"收到客户端截图上传: {filename} (event={event_key}, api={upload_api}, ctime={client_time or '-'})", "api")

    # 返回相对路径供前端访问
    return jsonify({
        "status": "success",
        "message": "截图上传成功",
        "url": relative_url,
        "filename": filename,
        "event_key": event_key,
        "upload_api": upload_api,
        "client_time": client_time,
    })

@upload_bp.route('/api/upload/camera', methods=['POST'])
def upload_camera():
    if 'file' not in request.files:
        return jsonify({"error": "没有文件"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "文件名为空"}), 400

    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    event_key = _normalize_event_key(request.form.get('event_key'), timestamp)
    client_info = request.form.get('info', 'client_upload')
    client_name = (request.form.get('client_name', '终端取证客户端') or '终端取证客户端').strip()
    client_host = request.form.get('client_host', '').strip()
    client_ip = request.form.get('client_ip', '').strip()
    client_time = request.form.get('client_time', '').strip()
    upload_api = (request.form.get('upload_api', request.path) or request.path).strip()

    filename = f"camera_{event_key}.jpg"
    filepath = os.path.join(CAMERA_DIR, filename)

    file.save(filepath)

    relative_url = f"/uploads/camera/{filename}"
    server_time = now.strftime("%Y-%m-%d %H:%M:%S")
    _write_event_meta(event_key, 'camera', {
        'filename': filename,
        'url': relative_url,
        'upload_api': upload_api,
        'client_time': client_time,
        'client_name': client_name,
        'client_host': client_host,
        'client_ip': client_ip,
        'client_info': client_info,
        'server_time': server_time,
    })
    
    # 记录到系统日志
    from web.flask_app import append_log
    append_log("info", f"收到客户端摄像头上传: {filename} (event={event_key}, api={upload_api}, ctime={client_time or '-'})", "api")

    # 返回相对路径
    return jsonify({
        "status": "success",
        "message": "摄像头照片上传成功",
        "url": relative_url,
        "filename": filename,
        "event_key": event_key,
        "upload_api": upload_api,
        "client_time": client_time,
    })

@upload_bp.route('/api/upload/list', methods=['GET'])
def list_uploads():
    """获取聚合后的终端取证事件列表（截图+摄像头记为一次攻击）。"""
    return jsonify(collect_terminal_evidence())
