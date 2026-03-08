#!/usr/bin/env python3
"""
数据库优化脚本

功能：
  1. VACUUM — 回收空闲页面，压缩数据库文件
  2. ANALYZE — 更新查询优化器统计信息
  3. integrity_check — 校验数据库完整性
  4. 检查表大小并给出归档建议
  5. 检查缺失索引

用法：
  python scripts/optimize_db.py
  python scripts/optimize_db.py --db backend/aimiguard.db
  python scripts/optimize_db.py --skip-vacuum   # 跳过 VACUUM（大库耗时长）
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "aimiguard.db"

# 超过此行数的表建议归档
ARCHIVE_THRESHOLD = 100_000


def get_table_stats(conn: sqlite3.Connection) -> list[dict]:
    """获取所有表的行数统计"""
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()

    stats = []
    for (name,) in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
        except Exception:
            count = -1
        stats.append({"table": name, "rows": count})
    return stats


def check_indexes(conn: sqlite3.Connection) -> list[str]:
    """检查是否有表缺失索引"""
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()

    warnings = []
    for (name,) in tables:
        indexes = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name=?",
            (name,),
        ).fetchone()[0]
        row_count = conn.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
        if row_count > 1000 and indexes == 0:
            warnings.append(f"表 {name} 有 {row_count:,} 行但无索引")
    return warnings


def optimize_database(
    db_path: Path,
    skip_vacuum: bool = False,
) -> dict:
    """执行数据库优化"""
    if not db_path.exists():
        print(f"  ❌ 数据库不存在: {db_path}")
        return {"success": False, "error": "db_not_found"}

    size_before = db_path.stat().st_size
    print(f"  📂 数据库: {db_path}")
    print(f"  📏 当前大小: {size_before:,} bytes ({size_before / 1024 / 1024:.1f} MB)")
    print()

    conn = sqlite3.connect(str(db_path))

    # 1. 完整性校验
    print("  🔍 完整性校验...")
    result = conn.execute("PRAGMA integrity_check").fetchone()
    if result[0] != "ok":
        print(f"  ❌ 完整性异常: {result[0]}")
        conn.close()
        return {"success": False, "error": f"integrity: {result[0]}"}
    print("  ✅ 完整性校验通过")

    # 2. 表统计
    print("\n  📊 表统计:")
    stats = get_table_stats(conn)
    archive_candidates = []
    for s in sorted(stats, key=lambda x: x["rows"], reverse=True):
        marker = ""
        if s["rows"] >= ARCHIVE_THRESHOLD:
            marker = " ⚠️ 建议归档"
            archive_candidates.append(s["table"])
        print(f"     {s['table']:<35} {s['rows']:>10,} 行{marker}")

    # 3. 索引检查
    print("\n  🔑 索引检查...")
    index_warnings = check_indexes(conn)
    if index_warnings:
        for w in index_warnings:
            print(f"     ⚠️ {w}")
    else:
        print("     ✅ 所有大表均有索引")

    # 4. ANALYZE
    print("\n  📈 更新查询统计 (ANALYZE)...")
    conn.execute("ANALYZE")
    conn.commit()
    print("  ✅ ANALYZE 完成")

    # 5. VACUUM
    if skip_vacuum:
        print("\n  ⏭️ 跳过 VACUUM")
    else:
        print("\n  🗜️ 执行 VACUUM（可能耗时较长）...")
        conn.execute("VACUUM")
        conn.commit()
        size_after = db_path.stat().st_size
        saved = size_before - size_after
        print(f"  ✅ VACUUM 完成: {size_before:,} → {size_after:,} bytes (节省 {saved:,} bytes)")

    conn.close()

    size_after = db_path.stat().st_size
    return {
        "success": True,
        "size_before": size_before,
        "size_after": size_after,
        "table_count": len(stats),
        "total_rows": sum(s["rows"] for s in stats if s["rows"] >= 0),
        "archive_candidates": archive_candidates,
        "index_warnings": index_warnings,
    }


def main():
    parser = argparse.ArgumentParser(description="AimiGuard 数据库优化")
    parser.add_argument("--db", type=str, default=None, help="数据库路径")
    parser.add_argument("--skip-vacuum", action="store_true", help="跳过 VACUUM")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else DEFAULT_DB

    print("=" * 50)
    print("  AimiGuard 数据库优化")
    print("=" * 50)

    result = optimize_database(db_path, skip_vacuum=args.skip_vacuum)

    print("\n" + "=" * 50)
    if result["success"]:
        print(f"  ✅ 优化完成 — {result['table_count']} 张表, {result['total_rows']:,} 行")
        if result["archive_candidates"]:
            print(f"  ⚠️ 建议归档: {', '.join(result['archive_candidates'])}")
            print(f"     运行: python scripts/archive_old_data.py --days 90")
    print("=" * 50)
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
