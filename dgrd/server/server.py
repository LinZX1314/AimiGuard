from flask import Flask, request, jsonify
import os
import datetime

app = Flask(__name__)

# 服务器保存路径 - 修改为 web/vue/public/uploads 目录下，方便前端直接访问
BASE_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web", "vue", "public", "uploads")
SERVER_SCREENSHOT_DIR = os.path.join(BASE_UPLOAD_DIR, "screenshots")
SERVER_CAMERA_DIR = os.path.join(BASE_UPLOAD_DIR, "camera_photos")

# 确保目录存在
os.makedirs(SERVER_SCREENSHOT_DIR, exist_ok=True)
os.makedirs(SERVER_CAMERA_DIR, exist_ok=True)


@app.route('/')
def index():
    return jsonify({
        "status": "running",
        "message": "艾米盾财务中台图像接收服务",
        "endpoints": {
            "screenshot": "/upload/screenshot",
            "camera": "/upload/camera"
        }
    })


@app.route('/upload/screenshot', methods=['POST'])
def upload_screenshot():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{timestamp}.png"
    filepath = os.path.join(SERVER_SCREENSHOT_DIR, filename)

    file.save(filepath)
    # 返回相对路径，方便前端引用
    relative_path = f"/uploads/screenshots/{filename}"

    return jsonify({
        "status": "success",
        "message": "Screenshot uploaded successfully",
        "url": relative_path
    })


@app.route('/upload/camera', methods=['POST'])
def upload_camera():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"camera_{timestamp}.jpg"
    filepath = os.path.join(SERVER_CAMERA_DIR, filename)

    file.save(filepath)
    # 返回相对路径，方便前端引用
    relative_path = f"/uploads/camera_photos/{filename}"

    return jsonify({
        "status": "success",
        "message": "Camera photo uploaded successfully",
        "url": relative_path
    })


if __name__ == '__main__':
    print("=" * 50)
    print("艾米盾图像接收服务器启动...")
    print("监听地址: http://0.0.0.0:5001")
    print(f"存储路径: {BASE_UPLOAD_DIR}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5001, debug=False)
    app.run(host='0.0.0.0', port=5000, debug=False)
