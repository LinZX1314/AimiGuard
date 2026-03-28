#!/usr/bin/env python3
"""
AimiGuard  —— 玄枢·AI攻防指挥官
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
项目统一入口。
  python main.py          # 生产模式
  python main.py --debug  # 调试模式（Flask reloader）
"""
import os
import sys
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")

# 确保 web/ 和项目根目录都在 sys.path 中
for p in (BASE_DIR, WEB_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from utils.logger import log as unified_log

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")


def load_config() -> dict:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    config = load_config()
    server_cfg = config.get("server", {})
    host = server_cfg.get("host", "0.0.0.0")
    port = server_cfg.get("port", 5000)
    debug = server_cfg.get("debug", False)

    # 命令行 --debug 覆盖
    if "--debug" in sys.argv:
        debug = True

    if not host or not port:
        unified_log("Main", "关键服务器配置缺失 (host, port)", "ERROR")
        sys.exit(1)

    # 构建 Flask 应用
    from web.flask_app import create_app, print_startup_banner
    from web.api.runtime import start_runtime_workers

    app = create_app()

    # Flask debug 模式会启动两个进程，只在主进程中启动后台线程
    if debug:
        if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            unified_log("Main", "主进程启动后台线程 (Debug 模式)")
            start_runtime_workers()
            print_startup_banner(config)
        else:
            unified_log("Main", "初始进程，跳过后台线程 (等待主进程重载)", "WARN")
    else:
        unified_log("Main", "启动后台线程 (生产模式)")
        start_runtime_workers()
        print_startup_banner(config)

    # 屏蔽 Flask 启动横幅（"* Serving Flask app ..." 等提示）
    # 该输出由 flask.cli.show_server_banner 通过 click.secho 写入 stdout，
    # 与 Python logging 无关，必须 monkey-patch 才能屏蔽
    import flask.cli
    flask.cli.show_server_banner = lambda *a, **kw: None

    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    main()

