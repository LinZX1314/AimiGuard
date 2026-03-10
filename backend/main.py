import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.database import init_db
from core.logging_config import setup_logging
from core.response import (
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler,
)
from core.middleware import TraceIDMiddleware, RateLimitMiddleware
from api import auth, defense, scan, report, ai_chat, tts, stt, firewall, system, push, overview, plugin, device, workflow, realtime, fix_ticket, security_scan, honeypot, honeytoken, threat_intel, prompt_template, decoy, security_whitelist, notification
from services.scheduler_service import scheduler_service


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False)


def _read_server_config() -> tuple[str, int]:
    host = (os.getenv("APP_HOST") or os.getenv("HOST") or "0.0.0.0").strip() or "0.0.0.0"
    port_raw = (os.getenv("APP_PORT") or os.getenv("PORT") or "8000").strip() or "8000"
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise RuntimeError(f"环境变量 PORT 必须是整数，当前值: {port_raw}") from exc
    return host, port


DEFAULT_HOST, DEFAULT_PORT = _read_server_config()


def print_banner():
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     █████╗ ██╗███╗   ███╗██╗ ██████╗ ██╗   ██╗ █████╗ ███╗  ║
║    ██╔══██╗██║████╗ ████║██║██╔════╝ ██║   ██║██╔══██╗████╗ ║
║    ███████║██║██╔████╔██║██║██║  ███╗██║   ██║███████║██╔██╗║
║    ██╔══██║██║██║╚██╔╝██║██║██║   ██║██║   ██║██╔══██║██║╚██║
║    ██║  ██║██║██║ ╚═╝ ██║██║╚██████╔╝╚██████╔╝██║  ██║██║ ╚█║
║    ╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚╝
║                                                              ║
║              AI 驱动的智能安全运营平台 v0.1.0                 ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)
    print("🚀 系统启动中...")
    print(f"⏰ 启动时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    print_banner()
    init_db()
    print("✓ 数据库初始化完成")
    print("✓ API 路由注册完成")
    print("✓ 中间件加载完成")
    
    host = getattr(app.state, "server_host", DEFAULT_HOST)
    port = getattr(app.state, "server_port", DEFAULT_PORT)

    # 启动后台调度服务
    await scheduler_service.start()
    print("✓ 后台调度服务已启动")
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"🌐 服务地址: http://{host}:{port}")
    print(f"📚 API 文档: http://{host}:{port}/docs")
    print(f"🔧 健康检查: http://{host}:{port}/api/health")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ 系统启动成功！按 CTRL+C 停止服务")
    print()
    yield
    # Shutdown
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🛑 正在关闭服务...")
    
    # 停止后台调度服务
    await scheduler_service.stop()
    print("✓ 后台调度服务已停止")
    
    print("✓ 数据库连接已关闭")
    print("✓ 系统已安全退出")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


app = FastAPI(
    title="Aimiguan API",
    description="AI-driven Security Operations Platform",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.server_host = DEFAULT_HOST
app.state.server_port = DEFAULT_PORT

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TraceIDMiddleware)
app.add_middleware(RateLimitMiddleware, global_rpm=120, login_rpm=5)

# Register exception handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Register API routers
app.include_router(auth.router)
app.include_router(system.router)
app.include_router(system.compat_router)  # /api/system/* compatibility
app.include_router(defense.router)
app.include_router(defense.compat_router)
app.include_router(scan.router)
app.include_router(report.router)
app.include_router(ai_chat.router)
app.include_router(tts.router)
app.include_router(stt.router)
app.include_router(firewall.router)
app.include_router(push.router)
app.include_router(overview.router)
app.include_router(plugin.router)
app.include_router(device.router)
app.include_router(workflow.router)
app.include_router(realtime.router)
app.include_router(fix_ticket.router)
app.include_router(security_scan.router)
app.include_router(honeypot.router)
app.include_router(honeytoken.router)
app.include_router(threat_intel.router)
app.include_router(prompt_template.router)
app.include_router(decoy.router)
app.include_router(security_whitelist.router)
app.include_router(notification.router)


@app.get("/api/health")
async def health_check():
    return {
        "code": 0,
        "message": "OK",
        "data": {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
    }


@app.get("/")
async def root():
    return {"message": "Aimiguan API Server"}


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Aimiguan API Server")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"绑定主机地址 (默认: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"监听端口 (默认: {DEFAULT_PORT})")
    parser.add_argument("--workers", type=int, default=1, help="工作进程数 (默认: 1, 生产建议 4)")
    parser.add_argument("--dev", action="store_true", help="开发模式（热重载 + 详细日志）")
    args = parser.parse_args()

    os.environ["APP_HOST"] = args.host
    os.environ["APP_PORT"] = str(args.port)
    app.state.server_host = args.host
    app.state.server_port = args.port

    uvicorn.run(
        "main:app" if args.dev else app,
        host=args.host,
        port=args.port,
        workers=args.workers if not args.dev else 1,
        reload=args.dev,
        log_level="debug" if args.dev else "info",
    )
