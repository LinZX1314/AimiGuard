#!/usr/bin/env python3
"""
历史数据归档脚本

功能：
  1. 将超过指定天数的历史数据从主表导出到归档 SQLite 文件
  2. 归档后从主表删除对应记录（可选）
  3. 支持 dry-run 预览
  4. 归档表：threat_event, audit_log, scan_task, execution_task, plugin_call_log

用法：
  python scripts/archive_old_data.py --days 90
  python scripts/archive_old_data.py --days 90 --dry-run
  python scripts/archive_old_data.py --days 90 --purge   # 归档后删除源数据
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "aimiguard.db"
DEFAULT_ARCHIVE_DIR = PROJECT_ROOT / "backups" / "archives"

# 需归档的表及其时间列
ARCHIVABLE_TABLES = {
    "threat_event": "created_at",
    "audit_log": "created_at",
    "scan_task": "created_at",
    "execution_task": "created_at",
    "plugin_call_log": "created_at",
    "access_audit": "created_at",
}


def archive_table(
    source_conn: sqlite3.Connection,
    archive_conn: sqlite3.Connection,
    table: str,
    time_col: str,
    cutoff: str,
    purge: bool = False,
    dry_run: bool = False,
) -> int:
    """将单张表的过期数据归档"""
    # 检查表是否存在
    exists = source_conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()[0]
    if not exists:
        return 0

    # 统计待归档行数
    count = source_conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {time_col} < ?",
        (cutoff,),
    ).fetchone()[0]

    if count == 0:
        return 0

    if dry_run:
        print(f"  [DRY-RUN] {table}: {count} 行将被归档 (< {cutoff})")
        return count

    # 获取表结构
    create_sql = source_conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()[0]

    # 在归档库中创建表（如不存在）
    archive_conn.execute(create_sql.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS"))
    archive_conn.commit()

    # 导出数据
    rows = source_conn.execute(
        f"SELECT * FROM {table} WHERE {time_col} < ?",
        (cutoff,),
    ).fetchall()

    # 获取列数
    col_count = len(source_conn.execute(f"PRAGMA table_info({table})").fetchall())
    placeholders = ",".join(["?"] * col_count)

    archive_conn.executemany(
        f"INSERT OR IGNORE INTO {table} VALUES ({placeholders})",
        rows,
    )
    archive_conn.commit()

    # 可选删除源数据
    if purge:
        source_conn.execute(
            f"DELETE FROM {table} WHERE {time_col} < ?",
            (cutoff,),
        )
        source_conn.commit()
        print(f"  📦 {table}: {count} 行已归档并清除")
    else:
        print(f"  📦 {table}: {count} 行已归档（源数据保留）")

    return count


def archive_old_data(
    db_path: Path,
    archive_dir: Path,
    days: int = 90,
    purge: bool = False,
    dry_run: bool = False,
) -> dict:
    """执行历史数据归档"""
    if not db_path.exists():
        print(f"  ❌ 数据库不存在: {db_path}")
        return {"success": False, "error": "db_not_found"}

    archive_dir.mkdir(parents=True, exist_ok=True)

    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = archive_dir / f"archive_{timestamp}.db"

    print(f"  📂 源数据库: {db_path}")
    print(f"  📁 归档文件: {archive_path}")
    print(f"  📅 归档截止: {cutoff} ({days}天前)")
    if purge:
        print("  ⚠️  归档后将删除源数据")
    print()

    source_conn = sqlite3.connect(str(db_path))
    archive_conn = sqlite3.connect(str(archive_path)) if not dry_run else None

    total_rows = 0
    table_stats = {}

    for table, time_col in ARCHIVABLE_TABLES.items():
        count = archive_table(
            source_conn,
            archive_conn,
            table,
            time_col,
            cutoff,
            purge=purge,
            dry_run=dry_run,
        )
        if count > 0:
            table_stats[table] = count
            total_rows += count

    source_conn.close()
    if archive_conn:
        archive_conn.close()

    # 如果没有数据归档，删除空的归档文件
    if not dry_run and total_rows == 0 and archive_path.exists():
        archive_path.unlink()

    return {
        "success": True,
        "total_rows": total_rows,
        "tables": table_stats,
        "archive_file": str(archive_path) if total_rows > 0 else None,
        "cutoff": cutoff,
        "purge": purge,
        "dry_run": dry_run,
    }


def main():
    parser = argparse.ArgumentParser(description="AimiGuard 历史数据归档")
    parser.add_argument("--days", type=int, default=90, help="归档超过 N 天的数据（默认 90）")
    parser.add_argument("--db", type=str, default=None, help="数据库路径")
    parser.add_argument("--archive-dir", type=str, default=None, help="归档输出目录")
    parser.add_argument("--purge", action="store_true", help="归档后删除源数据")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else DEFAULT_DB
    archive_dir = Path(args.archive_dir) if args.archive_dir else DEFAULT_ARCHIVE_DIR

    print("=" * 50)
    print("  AimiGuard 历史数据归档")
    print("=" * 50)

    result = archive_old_data(db_path, archive_dir, args.days, args.purge, args.dry_run)

    if result["total_rows"] == 0:
        print("\n  ✅ 无需归档")
    else:
        print(f"\n  共归档 {result['total_rows']} 行数据")
        if result["archive_file"]:
            print(f"  归档文件: {result['archive_file']}")

    print("=" * 50)
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
