import mss
import mss.tools
import datetime


def capture_screenshot(event_key=None):
    """截取屏幕并返回内存图片数据（不落地文件）"""
    timestamp = event_key or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{timestamp}.png"

    try:
        # 截取主屏并编码为 PNG 字节流，避免在本地创建图片文件
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            shot = sct.grab(monitor)
            image_bytes = mss.tools.to_png(shot.rgb, shot.size)

        print(f"[截图] 已捕获内存图像: {filename}")
        return image_bytes
    except Exception as e:
        print(f"[截图] 捕获失败: {e}")
        return None
