#!/usr/bin/env python3
"""
数据库健康检查脚本

功能：
  1. 完整性校验（PRAGMA integrity_check）
  2. 文件大小与页面统计
  3. 关键表行数与增长趋势
  4. WAL/Journal 状态
  5. 索引使用率检查
  6. 输出健康评分与建议

用法：
  python scripts/check_db_health.py
  python scripts/check_db_health.py --db backend/aimiguard.db
  python scripts/check_db_health.py --json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "aimiguard.db"

# 关键业务表
KEY_TABLES = [
    "user", "role", "permission",
    "threat_event", "execution_task", "scan_task", "scan_finding",
    "audit_log", "ai_decision_log", "firewall_sync_task",
    "plugin_registry", "plugin_call_log",
    "honeypot_config", "honeytoken", "fix_ticket",
    "ip_whitelist",
]


def check_health(db_path: Path) -> dict:
    """执行数据库健康检查，返回报告"""
    report: dict = {
        "db_path": str(db_path),
        "exists": db_path.exists(),
        "healthy": True,
        "checks": {},
        "warnings": [],
        "suggestions": [],
    }

    if not db_path.exists():
        report["healthy"] = False
        report["warnings"].append("数据库文件不存在")
        return report

    # 文件大小
    size = db_path.stat().st_size
    report["file_size_bytes"] = size
    report["file_size_mb"] = round(size / 1024 / 1024, 2)

    conn = sqlite3.connect(str(db_path))

    # 1. 完整性校验
    result = conn.execute("PRAGMA integrity_check").fetchone()
    integrity_ok = result[0] == "ok"
    report["checks"]["integrity"] = {"ok": integrity_ok, "detail": result[0]}
    if not integrity_ok:
        report["healthy"] = False
        report["warnings"].append(f"完整性校验失败: {result[0]}")

    # 2. 页面统计
    page_count = conn.execute("PRAGMA page_count").fetchone()[0]
    page_size = conn.execute("PRAGMA page_size").fetchone()[0]
    free_pages = conn.execute("PRAGMA freelist_count").fetchone()[0]
    report["checks"]["pages"] = {
        "page_count": page_count,
        "page_size": page_size,
        "free_pages": free_pages,
        "fragmentation_pct": round(free_pages / max(page_count, 1) * 100, 1),
    }
    if free_pages > page_count * 0.2:
        report["suggestions"].append("碎片率较高，建议执行 VACUUM: python scripts/optimize_db.py")

    # 3. Journal 模式
    journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
    report["checks"]["journal_mode"] = journal

    # 4. 表统计
    all_tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    report["total_tables"] = len(all_tables)

    table_stats = {}
    total_rows = 0
    for (name,) in all_tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
        except Exception:
            count = -1
        table_stats[name] = count
        if count > 0:
            total_rows += count

    report["checks"]["tables"] = table_stats
    report["total_rows"] = total_rows

    # 5. 关键表检查
    missing_tables = [t for t in KEY_TABLES if t not in table_stats]
    if missing_tables:
        report["warnings"].append(f"缺失关键表: {', '.join(missing_tables)}")

    # 大表告警
    for name, count in table_stats.items():
        if count > 100_000:
            report["warnings"].append(f"表 {name} 行数 {count:,}，建议归档")
            report["suggestions"].append(f"python scripts/archive_old_data.py --days 90")

    # 6. 索引统计
    index_count = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='index'"
    ).fetchone()[0]
    report["checks"]["index_count"] = index_count

    # 7. RBAC 数据完整性
    try:
        user_count = conn.execute("SELECT COUNT(*) FROM user").fetchone()[0]
        role_count = conn.execute("SELECT COUNT(*) FROM role").fetchone()[0]
        perm_count = conn.execute("SELECT COUNT(*) FROM permission").fetchone()[0]
        report["checks"]["rbac"] = {
            "users": user_count,
            "roles": role_count,
            "permissions": perm_count,
        }
        if user_count == 0:
            report["warnings"].append("无用户数据，可能需要初始化")
        if role_count == 0:
            report["warnings"].append("无角色数据，RBAC 未初始化")
    except Exception:
        report["checks"]["rbac"] = {"error": "RBAC tables not found"}

    conn.close()

    # 总体健康评分
    score = 100
    score -= len(report["warnings"]) * 10
    score -= len(report["suggestions"]) * 5
    if not integrity_ok:
        score = 0
    report["health_score"] = max(0, min(100, score))

    return report


def main():
    parser = argparse.ArgumentParser(description="AimiGuard 数据库健康检查")
    parser.add_argument("--db", type=str, default=None, help="数据库路径")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else DEFAULT_DB
    report = check_health(db_path)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(0 if report["healthy"] else 1)

    print("=" * 55)
    print("  AimiGuard 数据库健康检查")
    print("=" * 55)

    if not report["exists"]:
        print(f"  ❌ 数据库不存在: {db_path}")
        sys.exit(1)

    print(f"  📂 路径: {report['db_path']}")
    print(f"  📏 大小: {report['file_size_mb']} MB ({report['file_size_bytes']:,} bytes)")
    print(f"  📊 表数: {report['total_tables']}    总行数: {report['total_rows']:,}")
    print(f"  📖 日志模式: {report['checks']['journal_mode']}")
    pages = report["checks"]["pages"]
    print(f"  📄 页面: {pages['page_count']:,} (碎片率 {pages['fragmentation_pct']}%)")
    print(f"  🔑 索引: {report['checks']['index_count']}")

    # 完整性
    ic = report["checks"]["integrity"]
    icon = "✅" if ic["ok"] else "❌"
    print(f"\n  {icon} 完整性: {ic['detail']}")

    # RBAC
    rbac = report["checks"].get("rbac", {})
    if "error" not in rbac:
        print(f"  👤 用户: {rbac.get('users', 0)}  角色: {rbac.get('roles', 0)}  权限: {rbac.get('permissions', 0)}")

    # 警告
    if report["warnings"]:
        print(f"\n  ⚠️  警告 ({len(report['warnings'])}):")
        for w in report["warnings"]:
            print(f"     • {w}")

    # 建议
    if report["suggestions"]:
        print(f"\n  💡 建议:")
        for s in report["suggestions"]:
            print(f"     • {s}")

    score = report["health_score"]
    if score >= 90:
        grade = "🟢 优秀"
    elif score >= 70:
        grade = "🟡 良好"
    elif score >= 50:
        grade = "🟠 一般"
    else:
        grade = "🔴 需修复"

    print(f"\n  健康评分: {score}/100 {grade}")
    print("=" * 55)
    sys.exit(0 if report["healthy"] else 1)


if __name__ == "__main__":
    main()
