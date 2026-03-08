#!/usr/bin/env python3
"""
队列堆积检查脚本

功能：
  1. 检查 execution_task 队列中待处理/执行中任务数
  2. 检查 scan_task 队列中待处理/运行中任务数
  3. 检查 firewall_sync_task 队列堆积
  4. 超过阈值时给出告警建议
  5. 输出 JSON 格式报告

用法：
  python scripts/check_queue_depth.py
  python scripts/check_queue_depth.py --db backend/aimiguard.db
  python scripts/check_queue_depth.py --json   # 仅输出 JSON
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "aimiguard.db"

# 队列定义: (表名, 状态列, 待处理状态列表, 告警阈值)
QUEUE_DEFINITIONS = [
    {
        "name": "execution_task",
        "label": "执行任务队列",
        "status_col": "status",
        "pending_states": ["pending", "approved"],
        "running_states": ["running"],
        "warn_threshold": 50,
        "critical_threshold": 200,
    },
    {
        "name": "scan_task",
        "label": "扫描任务队列",
        "status_col": "status",
        "pending_states": ["pending"],
        "running_states": ["running"],
        "warn_threshold": 20,
        "critical_threshold": 100,
    },
    {
        "name": "firewall_sync_task",
        "label": "防火墙同步队列",
        "status_col": "status",
        "pending_states": ["pending"],
        "running_states": ["syncing"],
        "warn_threshold": 30,
        "critical_threshold": 100,
    },
]


def check_queue(conn: sqlite3.Connection, qdef: dict) -> dict:
    """检查单个队列的深度"""
    table = qdef["name"]
    status_col = qdef["status_col"]

    # 检查表是否存在
    exists = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()[0]
    if not exists:
        return {
            "queue": table,
            "label": qdef["label"],
            "exists": False,
            "pending": 0,
            "running": 0,
            "total": 0,
            "level": "ok",
        }

    # 待处理
    pending_placeholders = ",".join(["?"] * len(qdef["pending_states"]))
    pending = conn.execute(
        f"SELECT COUNT(*) FROM [{table}] WHERE [{status_col}] IN ({pending_placeholders})",
        qdef["pending_states"],
    ).fetchone()[0]

    # 运行中
    running_placeholders = ",".join(["?"] * len(qdef["running_states"]))
    running = conn.execute(
        f"SELECT COUNT(*) FROM [{table}] WHERE [{status_col}] IN ({running_placeholders})",
        qdef["running_states"],
    ).fetchone()[0]

    # 全部
    total = conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]

    # 告警级别
    backlog = pending + running
    if backlog >= qdef["critical_threshold"]:
        level = "critical"
    elif backlog >= qdef["warn_threshold"]:
        level = "warning"
    else:
        level = "ok"

    return {
        "queue": table,
        "label": qdef["label"],
        "exists": True,
        "pending": pending,
        "running": running,
        "total": total,
        "level": level,
    }


def check_all_queues(db_path: Path) -> dict:
    """检查所有队列"""
    if not db_path.exists():
        return {"success": False, "error": "db_not_found", "queues": []}

    conn = sqlite3.connect(str(db_path))
    results = []
    overall_level = "ok"

    for qdef in QUEUE_DEFINITIONS:
        r = check_queue(conn, qdef)
        results.append(r)
        if r["level"] == "critical":
            overall_level = "critical"
        elif r["level"] == "warning" and overall_level != "critical":
            overall_level = "warning"

    conn.close()

    return {
        "success": True,
        "overall_level": overall_level,
        "queues": results,
    }


LEVEL_ICONS = {"ok": "✅", "warning": "⚠️", "critical": "🔴"}


def main():
    parser = argparse.ArgumentParser(description="AimiGuard 队列堆积检查")
    parser.add_argument("--db", type=str, default=None, help="数据库路径")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else DEFAULT_DB
    report = check_all_queues(db_path)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(0 if report["success"] else 1)

    print("=" * 55)
    print("  AimiGuard 队列堆积检查")
    print("=" * 55)

    if not report["success"]:
        print(f"  ❌ {report['error']}")
        sys.exit(1)

    print(f"\n  {'队列':<20} {'待处理':>8} {'运行中':>8} {'总量':>8}  状态")
    print(f"  {'─'*20} {'─'*8} {'─'*8} {'─'*8}  {'─'*6}")

    for q in report["queues"]:
        if not q["exists"]:
            print(f"  {q['label']:<20} {'(表不存在)':>26}")
            continue
        icon = LEVEL_ICONS.get(q["level"], "")
        print(f"  {q['label']:<20} {q['pending']:>8,} {q['running']:>8,} {q['total']:>8,}  {icon} {q['level']}")

    print(f"\n  总体状态: {LEVEL_ICONS[report['overall_level']]} {report['overall_level']}")

    if report["overall_level"] == "critical":
        print("\n  🔴 存在队列严重堆积！请检查执行器/扫描器服务是否正常运行。")
    elif report["overall_level"] == "warning":
        print("\n  ⚠️ 队列有一定堆积，建议关注。")

    print("=" * 55)
    sys.exit(0 if report["overall_level"] != "critical" else 2)


if __name__ == "__main__":
    main()
