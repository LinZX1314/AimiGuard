import requests
from config import SCREENSHOT_ENDPOINT, CAMERA_ENDPOINT, UPLOAD_TIMEOUT


def upload_screenshot(filepath):
    """上传截图到服务器"""
    if not filepath:
        print("[上传] 截图文件不存在，跳过上传")
        return False

    try:
        with open(filepath, 'rb') as f:
            files = {'file': f}
            response = requests.post(
                SCREENSHOT_ENDPOINT,
                files=files,
                timeout=UPLOAD_TIMEOUT
            )

        if response.status_code == 200:
            print(f"[上传] 截图上传成功: {filepath}")
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


def upload_camera_photo(filepath):
    """上传摄像头照片到服务器"""
    if not filepath:
        print("[上传] 摄像头照片文件不存在，跳过上传")
        return False

    try:
        with open(filepath, 'rb') as f:
            files = {'file': f}
            response = requests.post(
                CAMERA_ENDPOINT,
                files=files,
                timeout=UPLOAD_TIMEOUT
            )

        if response.status_code == 200:
            print(f"[上传] 摄像头照片上传成功: {filepath}")
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
