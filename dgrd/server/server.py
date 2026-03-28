from flask import Flask, request, jsonify
import os
import datetime
import json

app = Flask(__name__)

# 服务器保存路径 - 修改为 web/vue/public/uploads 目录下，方便前端直接访问
BASE_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web", "vue", "public", "uploads")
SERVER_SCREENSHOT_DIR = os.path.join(BASE_UPLOAD_DIR, "screenshots")
SERVER_CAMERA_DIR = os.path.join(BASE_UPLOAD_DIR, "camera_photos")
TERMINAL_META_DIR = os.path.join(BASE_UPLOAD_DIR, "terminal_meta")

# 确保目录存在
os.makedirs(SERVER_SCREENSHOT_DIR, exist_ok=True)
os.makedirs(SERVER_CAMERA_DIR, exist_ok=True)
os.makedirs(TERMINAL_META_DIR, exist_ok=True)


def _normalize_ip(raw_ip: str | None) -> str:
    return str(raw_ip or '').split(',')[0].strip()


def _is_usable_ip(ip: str) -> bool:
    if not ip:
        return False
    lower = ip.lower()
    if lower in {'0.0.0.0', '::', '::1', 'unknown'}:
        return False
    if ip.startswith('127.'):
        return False
    return True


def _extract_terminal_ip(req):
    candidates = [
        req.form.get('terminal_ip', ''),
        req.form.get('client_ip', ''),
        req.headers.get('X-Real-IP', ''),
        req.headers.get('X-Forwarded-For', ''),
        req.remote_addr or '',
    ]
    for raw in candidates:
        ip = _normalize_ip(raw)
        if _is_usable_ip(ip):
            return ip

    for raw in candidates:
        ip = _normalize_ip(raw)
        if ip:
            return ip
    return ''


def _meta_file_path(event_key: str) -> str:
    return os.path.join(TERMINAL_META_DIR, f"{event_key}.json")


def _read_meta(event_key: str) -> dict:
    path = _meta_file_path(event_key)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_meta(event_key: str, capture_type: str, payload: dict):
    meta = _read_meta(event_key)
    channels = meta.get('channels') if isinstance(meta.get('channels'), dict) else {}
    channels[capture_type] = {
        'filename': payload.get('filename') or '',
        'url': payload.get('url') or '',
        'upload_api': payload.get('upload_api') or '',
        'client_time': payload.get('client_time') or '',
        'terminal_ip': payload.get('terminal_ip') or '',
        'server_time': payload.get('server_time') or '',
    }

    meta.update({
        'event_key': event_key,
        'client_name': payload.get('client_name') or meta.get('client_name') or '',
        'client_host': payload.get('client_host') or meta.get('client_host') or '',
        'terminal_ip': payload.get('terminal_ip') or meta.get('terminal_ip') or '',
        'client_ip': payload.get('terminal_ip') or meta.get('client_ip') or '',
        'client_time': payload.get('client_time') or meta.get('client_time') or '',
        'upload_api': payload.get('upload_api') or meta.get('upload_api') or '',
        'channels': channels,
        'last_server_time': payload.get('server_time') or meta.get('last_server_time') or '',
    })

    with open(_meta_file_path(event_key), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


@app.route('/')
def index():
    return jsonify({
        "status": "running",
        "message": "艾米盾财务中台图像接收服务",
        "endpoints": {
            "screenshot": "/upload/screenshot",
            "camera": "/upload/camera"
        }
    })


@app.route('/upload/screenshot', methods=['POST'])
def upload_screenshot():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400

    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    event_key = (request.form.get('event_key') or '').strip() or timestamp
    client_time = (request.form.get('client_time') or '').strip()
    upload_api = (request.form.get('upload_api') or request.path).strip()
    client_name = (request.form.get('client_name') or '').strip()
    client_host = (request.form.get('client_host') or '').strip()
    terminal_ip = _extract_terminal_ip(request)

    filename = f"screenshot_{event_key}.png"
    filepath = os.path.join(SERVER_SCREENSHOT_DIR, filename)

    file.save(filepath)
    # 返回相对路径，方便前端引用
    relative_path = f"/uploads/screenshots/{filename}"

    _write_meta(event_key, 'screenshot', {
        'filename': filename,
        'url': relative_path,
        'upload_api': upload_api,
        'client_time': client_time,
        'client_name': client_name,
        'client_host': client_host,
        'terminal_ip': terminal_ip,
        'server_time': now.strftime("%Y-%m-%d %H:%M:%S"),
    })

    return jsonify({
        "status": "success",
        "message": "Screenshot uploaded successfully",
        "url": relative_path,
        "event_key": event_key,
        "upload_api": upload_api,
        "client_time": client_time,
        "terminal_ip": terminal_ip,
    })


@app.route('/upload/camera', methods=['POST'])
def upload_camera():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400

    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    event_key = (request.form.get('event_key') or '').strip() or timestamp
    client_time = (request.form.get('client_time') or '').strip()
    upload_api = (request.form.get('upload_api') or request.path).strip()
    client_name = (request.form.get('client_name') or '').strip()
    client_host = (request.form.get('client_host') or '').strip()
    terminal_ip = _extract_terminal_ip(request)

    filename = f"camera_{event_key}.jpg"
    filepath = os.path.join(SERVER_CAMERA_DIR, filename)

    file.save(filepath)
    # 返回相对路径，方便前端引用
    relative_path = f"/uploads/camera_photos/{filename}"

    _write_meta(event_key, 'camera', {
        'filename': filename,
        'url': relative_path,
        'upload_api': upload_api,
        'client_time': client_time,
        'client_name': client_name,
        'client_host': client_host,
        'terminal_ip': terminal_ip,
        'server_time': now.strftime("%Y-%m-%d %H:%M:%S"),
    })

    return jsonify({
        "status": "success",
        "message": "Camera photo uploaded successfully",
        "url": relative_path,
        "event_key": event_key,
        "upload_api": upload_api,
        "client_time": client_time,
        "terminal_ip": terminal_ip,
    })


if __name__ == '__main__':
    print("=" * 50)
    print("艾米盾图像接收服务器启动...")
    print("监听地址: http://0.0.0.0:5001")
    print(f"存储路径: {BASE_UPLOAD_DIR}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5001, debug=False)
    app.run(host='0.0.0.0', port=5000, debug=False)
