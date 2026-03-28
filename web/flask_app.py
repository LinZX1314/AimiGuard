"""
AimiGuard Flask Application Factory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
create_app() -> Flask  —— 构建并返回完整配置的 Flask 实例。
所有路由、蓝图、中间件、SPA 静态文件均在此完成注册。
"""
import os

import logging
import threading
from datetime import datetime

from flask import Flask, Blueprint, jsonify, request, send_from_directory

import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database.db import init_db
from utils.logger import log as unified_log





# ── 日志缓冲（供 Web /api/logs 展示） ────────────────────────────────────────
_log_buffer: list[dict] = []
_LOG_MAX = 500
_log_lock = threading.Lock()


def append_log(level: str, message: str, category: str = "system"):
    """追加日志到内存缓冲，供前端日志页轮询拉取。"""
    with _log_lock:
        _log_buffer.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "message": message,
            "category": category,
        })
        if len(_log_buffer) > _LOG_MAX:
            _log_buffer.pop(0)


def _log(level: str, msg: str, category: str = "system"):
    """同时输出到控制台并追加到日志缓冲。"""
    unified_log("WebApp", msg, level.upper())
    append_log(level, msg, category)


# ── 应用工厂 ──────────────────────────────────────────────────────────────────

def create_app() -> Flask:
    """构建 Flask 应用：注册蓝图、中间件、SPA 路由。"""
    app = Flask(__name__)

    # 关闭 Werkzeug 访问日志
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    # 初始化数据库
    init_db()
    _log("info", f"[{datetime.now()}] 统一数据库初始化完成", "system")

    # ── 注册 /api/v1/ 与 /api/ 蓝图 ──────────────────────────────────────
    try:
        from web.api import register_blueprints
        register_blueprints(app)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        unified_log("WebApp", f"/api/v1/ Blueprint 注册失败: {exc}", "WARN")

    # ── API 请求日志中间件 ────────────────────────────────────────────────
    @app.before_request
    def log_api_request():
        if (
            request.path.startswith("/api/")
            and request.path != "/api/logs"
        ):
            append_log("info", f"API {request.method} {request.path}", "api")

    # ── 日志 API ─────────────────────────────────────────────────────────
    @app.route("/api/logs")
    def api_logs():
        """获取系统日志（供 Web 日志页展示）。"""
        limit = _int_arg("limit", 200)
        category = request.args.get("category")
        with _log_lock:
            logs = list(_log_buffer)
        if category:
            logs = [l for l in logs if l.get("category") == category]
        return jsonify(logs[-limit:])

    # ── Vue SPA 静态文件 ─────────────────────────────────────────────────
    vue_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "vue-dist")

    @app.route("/")
    def spa_index():
        return send_from_directory(vue_dist, "index.html")

    @app.route("/assets/<path:filename>")
    def spa_assets(filename):
        return send_from_directory(os.path.join(vue_dist, "assets"), filename)

    @app.route("/favicon.ico")
    def spa_favicon():
        try:
            return send_from_directory(vue_dist, "favicon.ico")
        except Exception:
            return "", 204

    return app


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _int_arg(name: str, default: int) -> int:
    raw = request.args.get(name, default)
    try:
        return int(raw)
    except Exception:
        return default


def print_startup_banner(config: dict):
    """打印 玄枢·AI攻防指挥官 启动横幅及模块状态。"""
    server_cfg = config.get("server", {})
    host = server_cfg.get("host", "0.0.0.0")
    port = server_cfg.get("port", 5000)
    display_host = "localhost" if host in ("0.0.0.0", "127.0.0.1") else host

    ai_cfg = config.get("ai", {})
    ai_enabled = ai_cfg.get("enabled", False)
    auto_ban = ai_cfg.get("auto_ban", False)
    switches = config.get("switches", [])
    active_switches = [sw for sw in switches if isinstance(sw, dict) and sw.get('host') and sw.get('enabled', True)]

    unified_log("WebApp", "=" * 58)
    unified_log("WebApp", "玄枢·AI攻防指挥官 已启动")
    unified_log("WebApp", "=" * 58)
    unified_log("WebApp", f"控制台地址: http://{display_host}:{port}")
    unified_log("WebApp", (
        f"HFish 同步: {'已启用' if config.get('hfish', {}).get('sync_enabled') else '已禁用'}  |  "
        f"Nmap 扫描: {'已启用' if config.get('nmap', {}).get('scan_enabled') else '已禁用'}"
    ))
    unified_log("WebApp", (
        f"AI 分析: {'已启用' if ai_enabled else '已禁用'}  |  "
        f"ACL 自动封禁: {'已启用' if (ai_enabled and auto_ban and active_switches) else '已禁用'}"
    ))
    unified_log("WebApp", "=" * 58)

        f"AI 分析: {'已启用' if ai_enabled else '已禁用'}  |  "
        f"ACL 自动封禁: {'已启用' if (ai_enabled and auto_ban and active_switches) else '已禁用'}"
    ))
    unified_log("WebApp", "=" * 58)
