import requests
import datetime
import socket
import os
from urllib.parse import urlparse
from config import SCREENSHOT_ENDPOINT, CAMERA_ENDPOINT, UPLOAD_TIMEOUT, CLIENT_NAME, CLIENT_VERSION


def _is_usable_ip(ip: str) -> bool:
    return bool(ip and ip != '0.0.0.0' and not ip.startswith('127.'))


def _resolve_terminal_ip(hostname: str) -> str:
    # 优先使用出站网卡IP，避免 gethostbyname 返回 127.0.0.1
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('8.8.8.8', 80))
            ip = sock.getsockname()[0]
            if _is_usable_ip(ip):
                return ip
    except Exception:
        pass

    # 回退：主机名解析结果中挑选可用地址
    try:
        _, _, addr_list = socket.gethostbyname_ex(hostname)
        for ip in addr_list:
            if _is_usable_ip(ip):
                return ip
    except Exception:
        pass

    return ''


def _build_upload_payload(endpoint: str, capture_type: str, event_key: str | None, client_time: str | None):
    hostname = socket.gethostname()
    terminal_ip = _resolve_terminal_ip(hostname)
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
        # terminal_ip 作为主字段，client_ip 作为兼容字段保留
        'terminal_ip': terminal_ip,
        'client_ip': terminal_ip,
        'client_version': CLIENT_VERSION,
    }


def upload_screenshot(file_content, event_key=None, client_time=None, file_name=None):
    """上传截图到服务器（支持内存字节流直传）"""
    if not file_content:
        print("[上传] 截图数据不存在，跳过上传")
        return False

    try:
        default_name = file_name or f"screenshot_{event_key or datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        file_handle = None
        if isinstance(file_content, (bytes, bytearray, memoryview)):
            files = {'file': (default_name, file_content, 'image/png')}
            source_label = f"memory:{default_name}"
        elif isinstance(file_content, str) and os.path.exists(file_content):
            file_handle = open(file_content, 'rb')
            files = {'file': (os.path.basename(file_content), file_handle, 'image/png')}
            source_label = file_content
        else:
            print("[上传] 截图数据格式不支持，跳过上传")
            return False

        try:
            data = _build_upload_payload(SCREENSHOT_ENDPOINT, 'screenshot', event_key, client_time)
            response = requests.post(
                SCREENSHOT_ENDPOINT,
                files=files,
                data=data,
                timeout=UPLOAD_TIMEOUT
            )
        finally:
            if file_handle:
                file_handle.close()

        if response.status_code == 200:
            print(f"[上传] 截图上传成功: {source_label} (event={event_key or '-'}, api={data.get('upload_api')})")
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


def upload_camera_photo(file_content, event_key=None, client_time=None, file_name=None):
    """上传摄像头照片到服务器（支持内存字节流直传）"""
    if not file_content:
        print("[上传] 摄像头照片数据不存在，跳过上传")
        return False

    try:
        default_name = file_name or f"camera_{event_key or datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        file_handle = None
        if isinstance(file_content, (bytes, bytearray, memoryview)):
            files = {'file': (default_name, file_content, 'image/jpeg')}
            source_label = f"memory:{default_name}"
        elif isinstance(file_content, str) and os.path.exists(file_content):
            file_handle = open(file_content, 'rb')
            files = {'file': (os.path.basename(file_content), file_handle, 'image/jpeg')}
            source_label = file_content
        else:
            print("[上传] 摄像头照片数据格式不支持，跳过上传")
            return False

        try:
            data = _build_upload_payload(CAMERA_ENDPOINT, 'camera', event_key, client_time)
            response = requests.post(
                CAMERA_ENDPOINT,
                files=files,
                data=data,
                timeout=UPLOAD_TIMEOUT
            )
        finally:
            if file_handle:
                file_handle.close()

        if response.status_code == 200:
            print(f"[上传] 摄像头照片上传成功: {source_label} (event={event_key or '-'}, api={data.get('upload_api')})")
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
