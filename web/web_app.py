import os
import json
import threading
from datetime import datetime
from flask import Flask, jsonify, request

import sys

# 导入 MVC 模型层
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from database.db import init_db
from utils.logger import log as unified_log

app = Flask(__name__)

# 关闭Flask访问日志
import logging
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.WARNING)

# ── 注册 /api/v1/ Blueprint ──────────────────────────────────────────────────
try:
    from api_v1 import v1 as _v1_bp, legacy_api as _legacy_api_bp, start_runtime_workers
    app.register_blueprint(_v1_bp)
    app.register_blueprint(_legacy_api_bp)
    # /api/system/ai-config  ← reference frontend tries this prefix too
    from flask import Blueprint as _BP
    _sys = _BP('sys_compat', __name__, url_prefix='/api/system')

    @_sys.route('/ai-config', methods=['GET', 'POST'])
    def _sys_ai():
        from flask import request as _req
        from api_v1 import system_ai_config_get, system_ai_config_save
        if _req.method == 'GET':
            return system_ai_config_get()
        return system_ai_config_save()

    app.register_blueprint(_sys)
except Exception as _e:
    import traceback; traceback.print_exc()
    unified_log("WebApp", f"/api/v1/ Blueprint 注册失败: {_e}", "WARN")

# 配置路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# 加载配置
def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def reload_config():
    """从文件重新加载配置，支持动态更新"""
    global config
    try:
        config = load_config()
        return config
    except Exception as e:
        unified_log("WebApp", f"配置重载失败: {e}", "ERROR")
        return config


config = load_config()

# ==================== 日志缓冲（供 Web 展示） ====================
_log_buffer = []
_log_max = 500
_log_lock = threading.Lock()

def append_log(level, message, category="system"):
    """追加日志到缓冲，供 /api/logs 拉取"""
    cfg = config.get("logging", {})
    if category == "sync" and not cfg.get("sync_log", True):
        return
    if category == "scan" and not cfg.get("scan_log", True):
        return
    if category == "ai" and not cfg.get("ai_log", True):
        return
    if category == "error" and not cfg.get("error_log", True):
        return
    if category == "api" and not cfg.get("api_request_log", True):
        return
    with _log_lock:
        _log_buffer.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "message": message,
            "category": category
        })
        if len(_log_buffer) > _log_max:
            _log_buffer.pop(0)

# 扫描锁，防止同时执行多次扫描
is_scanning = False

# 启动时初始化数据库（每个进程都需要确保表存在）
init_db()

def _log(level, msg, category="system"):
    """同时输出到控制台并追加到日志缓冲"""
    unified_log("WebApp", msg, level.upper())
    append_log(level, msg, category)

_log("info", f"[{datetime.now()}] 统一数据库初始化完成", "system")

# ==================== 数据解析工具 ====================

def _int_arg(name, default):
    """读取并解析 query 参数中的整数值；非法值时回落默认值。"""
    raw = request.args.get(name, default)
    try:
        return int(raw)
    except Exception:
        return default

# ==================== 后台任务 ====================
# 任务实现已迁移到 api_v1.py，由 start_runtime_workers 统一托管。

# ==================== API 请求日志 ====================

@app.before_request
def log_api_request():
    """根据 config.logging.api_request_log 记录 API 请求"""
    if (request.path.startswith('/api/') and request.path != '/api/logs' and
            config.get("logging", {}).get("api_request_log", False)):
        append_log("info", f"API {request.method} {request.path}", "api")


# ==================== 路由 ====================

@app.route('/api/logs')
def api_logs():
    """获取系统日志（供 Web 日志页展示）"""
    limit = _int_arg('limit', 200)
    category = request.args.get('category')
    with _log_lock:
        logs = list(_log_buffer)
    if category:
        logs = [l for l in logs if l.get("category") == category]
    logs = logs[-limit:]
    return jsonify(logs)


# ======================================================
# Vue SPA 入口（仅 SPA 模式）
# 已移除旧 Jinja 页面与模板渲染路径。
# Vue Router 使用 hash 历史 (如 /#/hfish)，Flask 只需返回 index.html
# ======================================================
from flask import send_from_directory as _sfd

_VUE_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'vue-dist')

@app.route('/')
def spa_index():
    """Vue SPA 入口"""
    return _sfd(_VUE_DIST, 'index.html')

@app.route('/assets/<path:filename>')
def spa_assets(filename):
    """Vue SPA 静态资源"""
    return _sfd(os.path.join(_VUE_DIST, 'assets'), filename)

@app.route('/favicon.ico')
def spa_favicon():
    try: return _sfd(_VUE_DIST, 'favicon.ico')
    except: return '', 204


def print_startup_banner():
    """打印 玄枢·AI攻防指挥官 启动横幅及模块状态"""
    server_config = config.get('server', {})
    host = server_config.get('host', '0.0.0.0')
    port = server_config.get('port', 5000)
    display_host = 'localhost' if host in ('0.0.0.0', '127.0.0.1') else host
    ai_cfg = config.get('ai', {})
    ai_enabled = ai_cfg.get('enabled', False)
    auto_ban = ai_cfg.get('auto_ban', False)
    switches = config.get('switches', [])

    unified_log("WebApp", "=" * 58)
    unified_log("WebApp", "[*] 玄枢·AI攻防指挥官 已启动")
    unified_log("WebApp", "=" * 58)
    unified_log("WebApp", f"控制台地址: http://{display_host}:{port}")
    unified_log("WebApp", f"HFish 同步: {'已启用' if config.get('hfish', {}).get('sync_enabled') else '已禁用'}  |  Nmap 扫描: {'已启用' if config.get('nmap', {}).get('scan_enabled') else '已禁用'}")
    unified_log("WebApp", f"AI 分析: {'已启用' if ai_enabled else '已禁用'}  |  ACL 自动封禁: {'已启用' if (ai_enabled and auto_ban and switches) else '已禁用'}")
    unified_log("WebApp", "=" * 58)


if __name__ == '__main__':

    server_config = config.get('server', {})
    host = server_config.get('host', '0.0.0.0')
    port = server_config.get('port', 5000)
    debug_mode = server_config.get('debug', False)

    # 如果关键服务器配置缺失，则报错提示或退出
    if not host or not port:
        unified_log("WebApp", "关键服务器配置缺失 (host, port)", "ERROR")
        sys.exit(1)

    # Flask debug 模式会启动两个进程：
    # 只在主运行环境中启动后台线程，防止端口占用和重复启动
    if debug_mode:
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            unified_log("WebApp", "主进程启动后台线程 (Debug模式)")
            start_runtime_workers()
            print_startup_banner()
        else:
            unified_log("WebApp", "初始进程，跳过后台线程 (等待主进程重载)", "WARN")
    else:
        unified_log("WebApp", "启动后台线程 (生产模式)")
        start_runtime_workers()
        print_startup_banner()

    app.run(host=host, port=port, debug=debug_mode)
