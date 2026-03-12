"""统一日志工具模块"""
from datetime import datetime


def log(module, message, level="INFO"):
    """统一日志格式输出

    Args:
        module: 模块名称，如 WebApp, HFish, Nmap, AI, Network
        message: 日志消息
        level: 日志级别，可选 INFO, WARN, ERROR, DEBUG
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level:5}] [{module:10}] {message}")
