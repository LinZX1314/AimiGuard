import os
import sys
from pathlib import Path


def _normalize_server_url(raw_url: str) -> str:
	value = (raw_url or "").strip()
	if not value:
		return ""
	if not value.startswith(("http://", "https://")):
		value = f"http://{value}"
	return value.rstrip("/")


def _runtime_dir() -> Path:
	# 打包后的 exe 读取其所在目录；源码运行时读取当前文件目录。
	if getattr(sys, "frozen", False):
		return Path(sys.executable).resolve().parent
	return Path(__file__).resolve().parent


def _load_server_url_from_file() -> str:
	cfg_path = _runtime_dir() / "server_url.txt"
	if not cfg_path.exists():
		return ""
	try:
		return _normalize_server_url(cfg_path.read_text(encoding="utf-8").strip())
	except Exception:
		return ""


def _load_server_url_from_embedded() -> str:
	try:
		from build_server_url import SERVER_URL as embedded_server_url
		return _normalize_server_url(str(embedded_server_url))
	except Exception:
		return ""


def _resolve_server_url() -> str:
	# 优先级：打包内嵌 URL > 环境变量 > 同目录 server_url.txt > 默认本机地址。
	embedded_url = _load_server_url_from_embedded()
	if embedded_url:
		return embedded_url

	env_url = _normalize_server_url(os.getenv("AIMIGUARD_SERVER_URL", ""))
	if env_url:
		return env_url

	file_url = _load_server_url_from_file()
	if file_url:
		return file_url

	# 默认值仅适合服务端本机运行；分发给他人时建议配置 server_url.txt。
	return "http://127.0.0.1:5000"


# 服务器配置
SERVER_URL = _resolve_server_url()

# 上传端点 - 统一到主系统 Web API (/api/upload/...)
SCREENSHOT_ENDPOINT = f"{SERVER_URL}/api/upload/screenshot"
CAMERA_ENDPOINT = f"{SERVER_URL}/api/upload/camera"

# 超时设置（秒）
UPLOAD_TIMEOUT = 30

# 客户端标识（用于后端展示取证来源与API/时间元数据）
CLIENT_NAME = "AimiGuardCounterClient"
CLIENT_VERSION = "1.0.0"
