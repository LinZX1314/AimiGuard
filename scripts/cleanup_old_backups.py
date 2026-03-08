#!/usr/bin/env python3
"""
过期备份清理脚本

功能：
  1. 扫描备份目录，删除超过保留天数的备份文件
  2. 支持按文件大小统计释放空间
  3. 支持 dry-run 模式预览

用法：
  python scripts/cleanup_old_backups.py --days 30
  python scripts/cleanup_old_backups.py --days 7 --dry-run
  python scripts/cleanup_old_backups.py --days 30 --backup-dir backups/
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "backups"


def cleanup_old_backups(
    backup_dir: Path,
    retain_days: int = 30,
    dry_run: bool = False,
) -> dict:
    """清理超过保留天数的旧备份文件"""
    if not backup_dir.exists():
        print(f"  备份目录不存在: {backup_dir}")
        return {"removed": [], "freed_bytes": 0}

    cutoff = time.time() - retain_days * 86400
    removed = []
    freed_bytes = 0

    # 扫描所有备份文件（含校验和文件）
    for f in sorted(backup_dir.iterdir()):
        if not f.is_file():
            continue
        if not f.name.startswith("aimiguard_"):
            continue
        if f.stat().st_mtime >= cutoff:
            continue

        size = f.stat().st_size
        if dry_run:
            print(f"  [DRY-RUN] 将删除: {f.name}  ({size:,} bytes)")
        else:
            f.unlink()
            print(f"  🗑️ 已删除: {f.name}  ({size:,} bytes)")
        removed.append(f.name)
        freed_bytes += size

    return {"removed": removed, "freed_bytes": freed_bytes}


def main():
    parser = argparse.ArgumentParser(description="AimiGuard 过期备份清理")
    parser.add_argument("--days", type=int, default=30, help="保留天数（默认 30）")
    parser.add_argument("--backup-dir", type=str, default=None, help="备份目录")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际删除")
    args = parser.parse_args()

    backup_dir = Path(args.backup_dir) if args.backup_dir else DEFAULT_BACKUP_DIR

    print("=" * 50)
    print("  AimiGuard 过期备份清理")
    print("=" * 50)
    print(f"  📁 备份目录: {backup_dir}")
    print(f"  📅 保留天数: {args.days}")
    if args.dry_run:
        print("  ⚠️  DRY-RUN 模式（不实际删除）")
    print()

    result = cleanup_old_backups(backup_dir, args.days, args.dry_run)

    count = len(result["removed"])
    freed = result["freed_bytes"]
    if count == 0:
        print("  ✅ 无需清理")
    else:
        action = "将清理" if args.dry_run else "已清理"
        print(f"\n  {action} {count} 个文件，释放 {freed:,} bytes ({freed / 1024 / 1024:.1f} MB)")

    print("=" * 50)


if __name__ == "__main__":
    main()
