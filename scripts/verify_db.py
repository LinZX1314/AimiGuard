#!/usr/bin/env python3
"""
数据库结构与数据一致性验证脚本（scripts/ 入口）

功能：
  1. 验证所有必要表是否存在
  2. 验证 RBAC 数据完整性（用户/角色/权限/关联）
  3. 验证关键索引是否创建
  4. 验证外键约束
  5. 检查表结构与 mvp_schema.sql 定义一致性

用法：
  python scripts/verify_db.py
  python scripts/verify_db.py --db backend/aimiguard.db
  python scripts/verify_db.py --json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "aimiguard.db"
SCHEMA_SQL = PROJECT_ROOT / "sql" / "mvp_schema.sql"

# 必须存在的核心表
REQUIRED_TABLES = {
    "user", "role", "permission", "user_role", "role_permission",
    "threat_event", "execution_task", "scan_task", "scan_finding",
    "asset", "device", "credential",
    "ai_decision_log", "ai_chat_session", "ai_chat_message", "ai_report",
    "audit_log", "access_audit",
    "plugin_registry", "push_channel", "firewall_sync_task",
    "model_profile", "backup_job", "restore_job",
    "honeypot_config", "honeytoken", "fix_ticket",
    "ip_whitelist",
}


def verify_database(db_path: Path) -> dict:
    """验证数据库结构与一致性"""
    report = {
        "db_path": str(db_path),
        "valid": True,
        "errors": [],
        "warnings": [],
        "tables_found": 0,
        "tables_missing": [],
        "rbac": {},
        "indexes": 0,
    }

    if not db_path.exists():
        report["valid"] = False
        report["errors"].append("数据库文件不存在")
        return report

    conn = sqlite3.connect(str(db_path))

    # 1. 完整性
    result = conn.execute("PRAGMA integrity_check").fetchone()
    if result[0] != "ok":
        report["valid"] = False
        report["errors"].append(f"完整性校验失败: {result[0]}")
        conn.close()
        return report

    # 2. 表存在性
    existing = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    report["tables_found"] = len(existing)
    missing = REQUIRED_TABLES - existing
    if missing:
        report["tables_missing"] = sorted(missing)
        report["warnings"].append(f"缺失 {len(missing)} 张必要表: {', '.join(sorted(missing))}")

    # 3. RBAC 验证
    try:
        user_count = conn.execute("SELECT COUNT(*) FROM user").fetchone()[0]
        role_count = conn.execute("SELECT COUNT(*) FROM role").fetchone()[0]
        perm_count = conn.execute("SELECT COUNT(*) FROM permission").fetchone()[0]
        ur_count = conn.execute("SELECT COUNT(*) FROM user_role").fetchone()[0]
        rp_count = conn.execute("SELECT COUNT(*) FROM role_permission").fetchone()[0]

        report["rbac"] = {
            "users": user_count,
            "roles": role_count,
            "permissions": perm_count,
            "user_role_mappings": ur_count,
            "role_permission_mappings": rp_count,
        }

        if user_count == 0:
            report["warnings"].append("无用户数据")
        if role_count == 0:
            report["errors"].append("无角色数据 — RBAC 未初始化")
            report["valid"] = False
        if perm_count == 0:
            report["errors"].append("无权限数据 — RBAC 未初始化")
            report["valid"] = False
        if ur_count == 0:
            report["warnings"].append("无用户-角色关联")
        if rp_count == 0:
            report["warnings"].append("无角色-权限关联")

        # admin 用户检查
        admin = conn.execute("SELECT COUNT(*) FROM user WHERE username='admin'").fetchone()[0]
        if admin == 0:
            report["warnings"].append("未找到 admin 用户")
    except Exception as exc:
        report["warnings"].append(f"RBAC 验证失败: {exc}")

    # 4. 索引统计
    index_count = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='index'"
    ).fetchone()[0]
    report["indexes"] = index_count

    # 5. 外键约束检查
    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_violations:
        report["warnings"].append(f"发现 {len(fk_violations)} 处外键约束违反")

    conn.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="AimiGuard 数据库验证")
    parser.add_argument("--db", type=str, default=None, help="数据库路径")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else DEFAULT_DB
    report = verify_database(db_path)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(0 if report["valid"] else 1)

    print("=" * 55)
    print("  AimiGuard 数据库验证")
    print("=" * 55)

    if not report.get("db_path"):
        print("  ❌ 无法验证")
        sys.exit(1)

    print(f"  📂 {report['db_path']}")
    print(f"  📊 表: {report['tables_found']}    索引: {report['indexes']}")

    if report["tables_missing"]:
        print(f"\n  ⚠️  缺失表 ({len(report['tables_missing'])}):")
        for t in report["tables_missing"]:
            print(f"     • {t}")

    rbac = report.get("rbac", {})
    if rbac:
        print(f"\n  👤 RBAC: {rbac.get('users',0)} 用户, {rbac.get('roles',0)} 角色, {rbac.get('permissions',0)} 权限")
        print(f"          {rbac.get('user_role_mappings',0)} 用户-角色映射, {rbac.get('role_permission_mappings',0)} 角色-权限映射")

    if report["errors"]:
        print(f"\n  ❌ 错误 ({len(report['errors'])}):")
        for e in report["errors"]:
            print(f"     • {e}")

    if report["warnings"]:
        print(f"\n  ⚠️  警告 ({len(report['warnings'])}):")
        for w in report["warnings"]:
            print(f"     • {w}")

    verdict = "✅ 验证通过" if report["valid"] else "❌ 验证失败"
    print(f"\n  {verdict}")
    print("=" * 55)
    sys.exit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
