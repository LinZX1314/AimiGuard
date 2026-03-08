#!/usr/bin/env python3
"""
数据库备份脚本

功能：
  1. 全量备份 SQLite 数据库（使用 SQLite Online Backup API）
  2. 生成校验和确保备份完整性
  3. 自动清理过期备份（可配置保留天数）
  4. 支持压缩备份（gzip）
  5. 输出备份报告

用法：
  python scripts/backup_db.py                              # 默认备份
  python scripts/backup_db.py --db backend/aimiguard.db    # 指定数据库
  python scripts/backup_db.py --output backups/            # 指定输出目录
  python scripts/backup_db.py --compress                   # 压缩备份
  python scripts/backup_db.py --retain-days 30             # 保留30天
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "aimiguard.db"
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "backups"


def compute_sha256(filepath: Path) -> str:
    """计算文件 SHA256 校验和"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def backup_database(
    db_path: Path,
    backup_dir: Path,
    compress: bool = False,
    label: str = "",
) -> dict:
    """
    执行数据库备份。

    使用 SQLite 的 backup API 确保一致性快照。
    """
    if not db_path.exists():
        print(f"  ❌ 数据库不存在: {db_path}")
        return {"success": False, "error": "database_not_found"}

    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label_suffix = f"_{label}" if label else ""
    backup_name = f"aimiguard_{timestamp}{label_suffix}.db"
    backup_path = backup_dir / backup_name

    print(f"  📂 源数据库: {db_path}")
    print(f"  📁 备份目录: {backup_dir}")

    # 1. 使用 SQLite backup API 创建一致性快照
    try:
        source_conn = sqlite3.connect(str(db_path))
        dest_conn = sqlite3.connect(str(backup_path))
        source_conn.backup(dest_conn)
        dest_conn.close()
        source_conn.close()
    except Exception as exc:
        print(f"  ❌ 备份失败: {exc}")
        return {"success": False, "error": str(exc)}

    # 2. 验证备份完整性
    try:
        verify_conn = sqlite3.connect(str(backup_path))
        result = verify_conn.execute("PRAGMA integrity_check").fetchone()
        verify_conn.close()
        if result[0] != "ok":
            print(f"  ⚠️ 备份完整性校验失败: {result[0]}")
            return {"success": False, "error": f"integrity_check_failed: {result[0]}"}
    except Exception as exc:
        print(f"  ⚠️ 完整性校验出错: {exc}")

    # 3. 计算校验和
    checksum = compute_sha256(backup_path)
    source_checksum = compute_sha256(db_path)
    file_size = backup_path.stat().st_size

    # 4. 可选压缩
    final_path = backup_path
    if compress:
        gz_path = backup_path.with_suffix(".db.gz")
        with open(backup_path, "rb") as f_in:
            with gzip.open(gz_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        backup_path.unlink()
        final_path = gz_path
        compressed_size = gz_path.stat().st_size
        ratio = compressed_size / file_size * 100 if file_size > 0 else 0
        print(f"  🗜️ 压缩: {file_size:,} → {compressed_size:,} bytes ({ratio:.1f}%)")
        file_size = compressed_size

    # 5. 写入校验和文件
    checksum_path = final_path.with_suffix(final_path.suffix + ".sha256")
    checksum_path.write_text(f"{checksum}  {final_path.name}\n", encoding="utf-8")

    print(f"  ✅ 备份完成: {final_path.name}")
    print(f"  📏 大小: {file_size:,} bytes")
    print(f"  🔑 SHA256: {checksum[:16]}...")

    return {
        "success": True,
        "backup_file": str(final_path),
        "backup_name": final_path.name,
        "source_db": str(db_path),
        "source_checksum": source_checksum,
        "backup_checksum": checksum,
        "file_size": file_size,
        "compressed": compress,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def cleanup_old_backups(backup_dir: Path, retain_days: int = 30) -> list[str]:
    """清理超过保留天数的旧备份"""
    if not backup_dir.exists():
        return []

    import time
    cutoff = time.time() - retain_days * 86400
    removed = []

    for f in backup_dir.iterdir():
        if f.name.startswith("aimiguard_") and f.stat().st_mtime < cutoff:
            f.unlink()
            removed.append(f.name)

    if removed:
        print(f"  🗑️ 清理 {len(removed)} 个过期备份 (>{retain_days}天)")
    return removed


def list_backups(backup_dir: Path) -> list[dict]:
    """列出所有备份"""
    if not backup_dir.exists():
        return []

    backups = []
    for f in sorted(backup_dir.glob("aimiguard_*.db*")):
        if f.suffix == ".sha256":
            continue
        backups.append({
            "name": f.name,
            "size": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            "path": str(f),
        })
    return backups


def main():
    parser = argparse.ArgumentParser(description="AimiGuard 数据库备份")
    parser.add_argument("--db", type=str, default=None, help="数据库路径")
    parser.add_argument("--output", type=str, default=None, help="备份输出目录")
    parser.add_argument("--compress", action="store_true", help="压缩备份 (gzip)")
    parser.add_argument("--retain-days", type=int, default=30, help="备份保留天数")
    parser.add_argument("--label", type=str, default="", help="备份标签后缀")
    parser.add_argument("--list", action="store_true", help="列出已有备份")
    parser.add_argument("--cleanup-only", action="store_true", help="仅清理过期备份")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else DEFAULT_DB
    backup_dir = Path(args.output) if args.output else DEFAULT_BACKUP_DIR

    print("=" * 50)
    print("  AimiGuard 数据库备份")
    print("=" * 50)

    if args.list:
        backups = list_backups(backup_dir)
        if not backups:
            print("  暂无备份")
        for b in backups:
            print(f"  {b['name']}  {b['size']:>10,} bytes  {b['modified']}")
        return

    if args.cleanup_only:
        removed = cleanup_old_backups(backup_dir, args.retain_days)
        if not removed:
            print("  无需清理")
        return

    # 执行备份
    result = backup_database(db_path, backup_dir, compress=args.compress, label=args.label)

    # 清理旧备份
    cleanup_old_backups(backup_dir, args.retain_days)

    # 输出报告
    report_path = backup_dir / "last_backup_report.json"
    report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=" * 50)
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
