import os
import mss
import datetime
from config import SCREENSHOT_DIR


def capture_screenshot():
    """截取屏幕并保存到本地文件夹"""
    # 确保目录存在
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    # 生成文件名
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{timestamp}.png"
    filepath = os.path.join(SCREENSHOT_DIR, filename)

    # 截取屏幕
    with mss.mss() as sct:
        sct.shot(output=filepath)

    print(f"[截图] 已保存到: {filepath}")
    return filepath
