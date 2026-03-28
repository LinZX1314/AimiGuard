import cv2
import datetime
import time


def capture_camera(event_key=None):
    """拍摄摄像头并返回内存图片数据（不落地文件）"""
    timestamp = event_key or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"camera_{timestamp}.jpg"

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
        success, encoded = cv2.imencode('.jpg', frame)
        if success and encoded is not None:
            print(f"[摄像头] 已捕获内存图像: {filename}")
            return encoded.tobytes()
        print("[摄像头] 图片编码失败")
        return None
    else:
        print(f"[摄像头] 拍摄失败 (ret={ret})")
        return None
