# 服务器配置 - 统一使用 AimiGuard 主系统的 5000 端口
SERVER_URL = "http://127.0.0.1:5000" 

# 上传端点 - 统一到主系统 Web API (/api/upload/...)
SCREENSHOT_ENDPOINT = f"{SERVER_URL}/api/upload/screenshot"
CAMERA_ENDPOINT = f"{SERVER_URL}/api/upload/camera"

# 超时设置（秒）
UPLOAD_TIMEOUT = 30

# 客户端标识（用于后端展示取证来源与API/时间元数据）
CLIENT_NAME = "AimiGuardCounterClient"
CLIENT_VERSION = "1.0.0"
