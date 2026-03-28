import requests
import datetime
import socket
from urllib.parse import urlparse
from config import SCREENSHOT_ENDPOINT, CAMERA_ENDPOINT, UPLOAD_TIMEOUT, CLIENT_NAME, CLIENT_VERSION


def _resolve_local_ip(hostname: str) -> str:
    try:
        return socket.gethostbyname(hostname)
    except Exception:
        return ''


def _build_upload_payload(endpoint: str, capture_type: str, event_key: str | None, client_time: str | None):
    hostname = socket.gethostname()
    local_ip = _resolve_local_ip(hostname)
    api_path = urlparse(endpoint).path or ''
    normalized_client_time = client_time or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        'info': 'client_upload',
        'capture_type': capture_type,
        'event_key': event_key or '',
        'client_time': normalized_client_time,
        'upload_api': api_path,
        'client_name': CLIENT_NAME,
        'client_host': hostname,
        'client_ip': local_ip,
        'client_version': CLIENT_VERSION,
    }


def upload_screenshot(filepath, event_key=None, client_time=None):
    """上传截图到服务器"""
    if not filepath:
        print("[上传] 截图文件不存在，跳过上传")
        return False

    try:
        with open(filepath, 'rb') as f:
            files = {'file': f}
            data = _build_upload_payload(SCREENSHOT_ENDPOINT, 'screenshot', event_key, client_time)
            response = requests.post(
                SCREENSHOT_ENDPOINT,
                files=files,
                data=data,
                timeout=UPLOAD_TIMEOUT
            )

        if response.status_code == 200:
            print(f"[上传] 截图上传成功: {filepath} (event={event_key or '-'}, api={data.get('upload_api')})")
            return True
        else:
            print(f"[上传] 截图上传失败: {response.status_code} - {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("[上传] 无法连接到服务器，请确保服务器正在运行")
        return False
    except Exception as e:
        print(f"[上传] 上传出错: {e}")
        return False


def upload_camera_photo(filepath, event_key=None, client_time=None):
    """上传摄像头照片到服务器"""
    if not filepath:
        print("[上传] 摄像头照片文件不存在，跳过上传")
        return False

    try:
        with open(filepath, 'rb') as f:
            files = {'file': f}
            data = _build_upload_payload(CAMERA_ENDPOINT, 'camera', event_key, client_time)
            response = requests.post(
                CAMERA_ENDPOINT,
                files=files,
                data=data,
                timeout=UPLOAD_TIMEOUT
            )

        if response.status_code == 200:
            print(f"[上传] 摄像头照片上传成功: {filepath} (event={event_key or '-'}, api={data.get('upload_api')})")
            return True
        else:
            print(f"[上传] 摄像头照片上传失败: {response.status_code} - {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("[上传] 无法连接到服务器，请确保服务器正在运行")
        return False
    except Exception as e:
        print(f"[上传] 上传出错: {e}")
        return False
