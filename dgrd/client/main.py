import screenshot
import camera
import uploader


def main():
    print("=" * 50)
    print("截图和摄像头拍照工具")
    print("=" * 50)

    # 1. 截取屏幕
    print("\n[步骤1] 截取屏幕...")
    screenshot_path = screenshot.capture_screenshot()

    # 2. 拍摄摄像头
    print("\n[步骤2] 拍摄摄像头...")
    camera_path = camera.capture_camera()

    # 3. 上传到服务器
    print("\n[步骤3] 上传到服务器...")
    uploader.upload_screenshot(screenshot_path)
    uploader.upload_camera_photo(camera_path)

    print("\n" + "=" * 50)
    print("完成!")
    print("=" * 50)


if __name__ == "__main__":
    main()
