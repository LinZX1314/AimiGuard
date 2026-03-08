"""
蜜罐端点与伪装路由（诱捕攻击者）

功能：
  1. 假管理后台登录页（/admin/login）— 记录所有访问者
  2. 假敏感 API（/api/v1/users/list）— 诱捕扫描器
  3. 假管理认证（/admin/auth）— 记录攻击者尝试的凭据
  4. 所有访问写入 audit_log 并触发告警

配置：
  环境变量 DECOY_ENABLED=true 启用（默认 false）
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger("aimiguan.decoy")

router = APIRouter(tags=["decoy"])

DECOY_ENABLED = os.getenv("DECOY_ENABLED", "false").lower() == "true"

FAKE_LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Admin Panel - Login</title>
  <style>
    body { font-family: Arial, sans-serif; background: #f5f5f5; display: flex;
           justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
    .login-box { background: #fff; padding: 40px; border-radius: 8px;
                 box-shadow: 0 2px 10px rgba(0,0,0,0.1); width: 320px; }
    h2 { text-align: center; color: #333; margin-bottom: 24px; }
    input { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ddd;
            border-radius: 4px; box-sizing: border-box; }
    button { width: 100%; padding: 10px; background: #4a90d9; color: #fff;
             border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
    button:hover { background: #357abd; }
    .footer { text-align: center; margin-top: 16px; color: #999; font-size: 12px; }
  </style>
</head>
<body>
  <div class="login-box">
    <h2>Admin Panel</h2>
    <form action="/admin/auth" method="post">
      <input type="text" name="username" placeholder="Username" required>
      <input type="password" name="password" placeholder="Password" required>
      <button type="submit">Sign In</button>
    </form>
    <div class="footer">© 2024 System Administration</div>
  </div>
</body>
</html>"""


async def _log_decoy_access(
    request: Request,
    path: str,
    reason: str,
    extra: dict | None = None,
):
    """记录蜜罐端点访问"""
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("X-Forwarded-For", "")
    user_agent = request.headers.get("User-Agent", "")

    log_data = {
        "client_ip": client_ip,
        "forwarded_for": forwarded,
        "path": path,
        "method": request.method,
        "user_agent": user_agent,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        log_data.update(extra)

    logger.warning(
        "DECOY_ACCESS: ip=%s path=%s reason=%s ua=%s",
        client_ip, path, reason, user_agent[:80],
    )

    # 尝试写入数据库审计
    try:
        from core.database import SessionLocal
        from services.audit_service import AuditService

        db = SessionLocal()
        try:
            AuditService.log(
                db=db,
                actor=f"decoy:{client_ip}",
                action="decoy_access",
                target=path,
                result=reason,
                trace_id=f"decoy_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                details=str(log_data),
            )
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.debug("Failed to write decoy audit: %s", exc)


@router.get("/admin/login")
async def fake_admin_login(request: Request):
    """伪装的管理后台登录页，记录所有访问者"""
    if not DECOY_ENABLED:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    await _log_decoy_access(request, "/admin/login", "访问伪装管理后台")
    return HTMLResponse(FAKE_LOGIN_HTML)


@router.post("/admin/auth")
async def fake_admin_auth(request: Request):
    """记录攻击者尝试的凭据"""
    if not DECOY_ENABLED:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    try:
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")
        password_hash = hashlib.sha256(password.encode()).hexdigest() if password else ""
    except Exception:
        username = ""
        password_hash = ""

    await _log_decoy_access(
        request,
        "/admin/auth",
        "尝试登录伪装管理后台",
        extra={"attempted_username": username, "password_hash": password_hash[:16]},
    )

    # 延迟响应，浪费攻击者时间
    await asyncio.sleep(3)

    return JSONResponse(
        status_code=401,
        content={"error": "Invalid credentials", "message": "Authentication failed"},
    )


@router.get("/api/v1/users/list")
async def fake_users_api(request: Request):
    """假的敏感 API，诱捕扫描器"""
    if not DECOY_ENABLED:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    await _log_decoy_access(request, "/api/v1/users/list", "访问伪装敏感API")

    # 返回假数据
    return {
        "users": [
            {"id": 1, "username": "admin", "role": "admin"},
            {"id": 2, "username": "test", "role": "user"},
        ]
    }


@router.get("/.env")
async def fake_env_file(request: Request):
    """诱捕扫描 .env 文件的攻击者"""
    if not DECOY_ENABLED:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    await _log_decoy_access(request, "/.env", "尝试读取环境变量文件")

    await asyncio.sleep(1)
    return JSONResponse(status_code=403, content={"detail": "Forbidden"})


@router.get("/wp-admin")
@router.get("/wp-login.php")
async def fake_wordpress(request: Request):
    """诱捕扫描 WordPress 的攻击者"""
    if not DECOY_ENABLED:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    await _log_decoy_access(request, request.url.path, "扫描WordPress路径")
    return HTMLResponse("<h1>WordPress is not installed</h1>", status_code=404)
