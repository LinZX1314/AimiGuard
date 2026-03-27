from flask import Flask, request, jsonify
import os
import datetime

app = Flask(__name__)

# 服务器保存路径
SERVER_SCREENSHOT_DIR = "server_screenshots"
SERVER_CAMERA_DIR = "server_camera_photos"

# 确保目录存在
os.makedirs(SERVER_SCREENSHOT_DIR, exist_ok=True)
os.makedirs(SERVER_CAMERA_DIR, exist_ok=True)


@app.route('/')
def index():
    return jsonify({
        "status": "running",
        "message": "截图和摄像头接收服务器",
        "endpoints": {
            "screenshot": "/upload/screenshot",
            "camera": "/upload/camera"
        }
    })


@app.route('/upload/screenshot', methods=['POST'])
def upload_screenshot():
    if 'file' not in request.files:
        return jsonify({"error": "没有文件"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "文件名为空"}), 400

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{timestamp}.png"
    filepath = os.path.join(SERVER_SCREENSHOT_DIR, filename)

    file.save(filepath)

    return jsonify({
        "status": "success",
        "message": "截图上传成功",
        "filename": filename,
        "path": filepath
    })


@app.route('/upload/camera', methods=['POST'])
def upload_camera():
    if 'file' not in request.files:
        return jsonify({"error": "没有文件"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "文件名为空"}), 400

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"camera_{timestamp}.jpg"
    filepath = os.path.join(SERVER_CAMERA_DIR, filename)

    file.save(filepath)

    return jsonify({
        "status": "success",
        "message": "摄像头照片上传成功",
        "filename": filename,
        "path": filepath
    })


if __name__ == '__main__':
    print("=" * 50)
    print("服务器启动中...")
    print("监听地址: http://localhost:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)
