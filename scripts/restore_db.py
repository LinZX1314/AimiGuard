#!/usr/bin/env python3
"""
数据库恢复脚本

功能：
  1. 从备份文件恢复数据库
  2. 支持 gzip 压缩备份恢复
  3. 恢复前自动校验完整性
  4. 恢复前自动备份当前数据库（安全网）
  5. 列出可用备份并按时间排序

用法：
  python scripts/restore_db.py --list                                    # 列出可用备份
  python scripts/restore_db.py --backup-file backups/aimiguard_xxx.db    # 从指定文件恢复
  python scripts/restore_db.py --latest                                  # 恢复最新备份
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "aimiguard.db"
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "backups"


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def list_backups(backup_dir: Path) -> list[dict]:
    """列出所有可用备份，按修改时间倒序"""
    if not backup_dir.exists():
        return []
    backups = []
    for f in sorted(backup_dir.glob("aimiguard_*.db*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.suffix == ".sha256":
            continue
        backups.append({
            "name": f.name,
            "size": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "path": str(f),
            "compressed": f.name.endswith(".gz"),
        })
    return backups


def verify_backup(backup_path: Path) -> tuple[bool, str]:
    """验证备份文件完整性"""
    if not backup_path.exists():
        return False, "文件不存在"

    # 检查校验和文件
    checksum_path = backup_path.with_suffix(backup_path.suffix + ".sha256")
    if checksum_path.exists():
        expected_line = checksum_path.read_text(encoding="utf-8").strip()
        expected_hash = expected_line.split()[0]
        actual_hash = compute_sha256(backup_path)
        if expected_hash != actual_hash:
            return False, f"SHA256 校验失败 (expected={expected_hash[:16]}..., actual={actual_hash[:16]}...)"

    # 如果是压缩文件，先解压到临时文件验证
    if backup_path.name.endswith(".gz"):
        try:
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            with gzip.open(backup_path, "rb") as f_in:
                with open(tmp_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            conn = sqlite3.connect(str(tmp_path))
            result = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            tmp_path.unlink()
            if result[0] != "ok":
                return False, f"SQLite 完整性校验失败: {result[0]}"
        except Exception as exc:
            return False, f"解压/校验失败: {exc}"
    else:
        try:
            conn = sqlite3.connect(str(backup_path))
            result = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            if result[0] != "ok":
                return False, f"SQLite 完整性校验失败: {result[0]}"
        except Exception as exc:
            return False, f"校验失败: {exc}"

    return True, "ok"


def restore_database(
    backup_path: Path,
    target_db: Path,
    skip_safety_backup: bool = False,
) -> dict:
    """从备份恢复数据库"""
    print(f"  📦 备份文件: {backup_path.name}")
    print(f"  🎯 目标数据库: {target_db}")

    # 1. 验证备份
    print("  🔍 验证备份完整性...")
    ok, reason = verify_backup(backup_path)
    if not ok:
        print(f"  ❌ 备份验证失败: {reason}")
        return {"success": False, "error": reason}
    print("  ✅ 备份验证通过")

    # 2. 安全备份当前数据库
    if target_db.exists() and not skip_safety_backup:
        safety_name = f"{target_db.stem}_pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}{target_db.suffix}"
        safety_path = target_db.parent / safety_name
        shutil.copy2(target_db, safety_path)
        print(f"  🛡️ 当前数据库已安全备份: {safety_name}")

    # 3. 恢复
    print("  ⏳ 正在恢复...")
    try:
        if backup_path.name.endswith(".gz"):
            with gzip.open(backup_path, "rb") as f_in:
                with open(target_db, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            shutil.copy2(backup_path, target_db)
    except Exception as exc:
        print(f"  ❌ 恢复失败: {exc}")
        return {"success": False, "error": str(exc)}

    # 4. 验证恢复后的数据库
    print("  🔍 验证恢复后数据库...")
    try:
        conn = sqlite3.connect(str(target_db))
        result = conn.execute("PRAGMA integrity_check").fetchone()
        tables = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()
        conn.close()
        if result[0] != "ok":
            print(f"  ⚠️ 恢复后完整性异常: {result[0]}")
            return {"success": False, "error": f"post_restore_integrity: {result[0]}"}
        print(f"  ✅ 恢复完成 — {tables[0]} 张表")
    except Exception as exc:
        print(f"  ⚠️ 验证出错: {exc}")

    return {
        "success": True,
        "backup_file": str(backup_path),
        "target_db": str(target_db),
        "timestamp": datetime.now().isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="AimiGuard 数据库恢复")
    parser.add_argument("--backup-file", type=str, default=None, help="备份文件路径")
    parser.add_argument("--latest", action="store_true", help="恢复最新备份")
    parser.add_argument("--db", type=str, default=None, help="目标数据库路径")
    parser.add_argument("--backup-dir", type=str, default=None, help="备份目录")
    parser.add_argument("--list", action="store_true", help="列出可用备份")
    parser.add_argument("--skip-safety", action="store_true", help="跳过安全备份（危险）")
    parser.add_argument("--yes", action="store_true", help="跳过确认提示")
    args = parser.parse_args()

    backup_dir = Path(args.backup_dir) if args.backup_dir else DEFAULT_BACKUP_DIR
    target_db = Path(args.db) if args.db else DEFAULT_DB

    print("=" * 50)
    print("  AimiGuard 数据库恢复")
    print("=" * 50)

    # 列出备份
    if args.list:
        backups = list_backups(backup_dir)
        if not backups:
            print("  暂无可用备份")
            return
        print(f"\n  {'序号':>4}  {'文件名':<45}  {'大小':>12}  {'时间'}")
        print(f"  {'─'*4}  {'─'*45}  {'─'*12}  {'─'*19}")
        for i, b in enumerate(backups, 1):
            gz = " 🗜️" if b["compressed"] else ""
            print(f"  {i:>4}  {b['name']:<45}  {b['size']:>10,} B  {b['modified']}{gz}")
        print(f"\n  共 {len(backups)} 个备份")
        return

    # 确定备份文件
    backup_path = None
    if args.backup_file:
        backup_path = Path(args.backup_file)
    elif args.latest:
        backups = list_backups(backup_dir)
        if not backups:
            print("  ❌ 无可用备份")
            sys.exit(1)
        backup_path = Path(backups[0]["path"])
        print(f"  📌 使用最新备份: {backup_path.name}")
    else:
        print("  请指定 --backup-file 或 --latest")
        sys.exit(1)

    if not backup_path.exists():
        print(f"  ❌ 备份文件不存在: {backup_path}")
        sys.exit(1)

    # 确认
    if not args.yes:
        print(f"\n  ⚠️  即将用 {backup_path.name} 覆盖 {target_db}")
        confirm = input("  确认恢复? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("  取消恢复")
            sys.exit(0)

    result = restore_database(backup_path, target_db, skip_safety_backup=args.skip_safety)
    print("=" * 50)
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
