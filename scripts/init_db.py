#!/usr/bin/env python3
"""
数据库初始化脚本（scripts/ 入口）

README 引用路径：scripts/init_db.py
实际逻辑委托给 backend/init_db.py

用法：
  python scripts/init_db.py
  python scripts/init_db.py --env production
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_INIT_DB = PROJECT_ROOT / "backend" / "init_db.py"


def main():
    parser = argparse.ArgumentParser(description="AimiGuard 数据库初始化")
    parser.add_argument("--env", type=str, default="dev", help="运行环境 (dev/production)")
    args = parser.parse_args()

    if not BACKEND_INIT_DB.exists():
        print(f"  ❌ 未找到后端初始化脚本: {BACKEND_INIT_DB}")
        sys.exit(1)

    print("=" * 50)
    print("  AimiGuard 数据库初始化")
    print("=" * 50)
    print(f"  📂 后端目录: {BACKEND_INIT_DB.parent}")
    print(f"  🌍 环境: {args.env}")
    print()

    # 如果是生产环境，设置环境变量
    env = os.environ.copy()
    if args.env == "production":
        env_prod = BACKEND_INIT_DB.parent / ".env.prod"
        if env_prod.exists():
            print(f"  📄 加载生产配置: {env_prod}")
            env["APP_ENV"] = "production"

    # 委托给 backend/init_db.py
    result = subprocess.run(
        [sys.executable, str(BACKEND_INIT_DB)],
        cwd=str(BACKEND_INIT_DB.parent),
        env=env,
    )

    if result.returncode == 0:
        print("\n  ✅ 数据库初始化完成")
    else:
        print(f"\n  ❌ 初始化失败 (exit code: {result.returncode})")

    print("=" * 50)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
