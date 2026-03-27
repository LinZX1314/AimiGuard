# 服务器配置
SERVER_URL = "http://192.168.0.3:5000"

# 本地保存路径
SCREENSHOT_DIR = "screenshots"
CAMERA_DIR = "camera_photos"

# 上传端点
SCREENSHOT_ENDPOINT = f"{SERVER_URL}/upload/screenshot"
CAMERA_ENDPOINT = f"{SERVER_URL}/upload/camera"

# 超时设置（秒）
UPLOAD_TIMEOUT = 30
