import os
import cv2
import datetime
import time
from config import CAMERA_DIR


def capture_camera():
    """拍摄摄像头照片并保存到本地文件夹"""
    # 确保目录存在
    os.makedirs(CAMERA_DIR, exist_ok=True)

    # 生成文件名
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"camera_{timestamp}.jpg"
    filepath = os.path.join(CAMERA_DIR, filename)

    # 尝试多个摄像头索引，使用 DirectShow 后端
    cap = None
    for camera_index in range(3):
        print(f"[摄像头] 尝试打开摄像头 {camera_index}...")
        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)

        if cap.isOpened():
            print(f"[摄像头] 成功打开摄像头 {camera_index}")
            break
        else:
            cap.release()
            cap = None

    if cap is None or not cap.isOpened():
        print("[摄像头] 无法打开任何摄像头")
        return None

    # 设置摄像头属性
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    # 等待摄像头初始化
    print("[摄像头] 等待摄像头初始化...")
    time.sleep(0.5)

    # 清空缓冲区
    for _ in range(5):
        cap.read()

    # 最终读取
    print("[摄像头] 拍摄照片...")
    ret, frame = None, None
    for _ in range(3):
        ret, frame = cap.read()
        if ret and frame is not None and frame.size > 0:
            break

    cap.release()

    if ret and frame is not None and frame.size > 0:
        success = cv2.imwrite(filepath, frame)
        if success:
            print(f"[摄像头] 已保存到: {filepath}")
            return filepath
        else:
            print("[摄像头] 保存图片失败")
            return None
    else:
        print(f"[摄像头] 拍摄失败 (ret={ret})")
        return None
