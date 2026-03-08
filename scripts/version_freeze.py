#!/usr/bin/env python3
"""
Step 10.6 — 正式放量上线并冻结版本

功能：
  1. 收集当前 git commit、branch、tag 信息
  2. 校验所有 Step 10 测试通过
  3. 记录版本到 release_history 表
  4. 生成版本冻结报告
  5. 建议创建 git tag

用法：
  python scripts/version_freeze.py                     # 生成报告（dry-run）
  python scripts/version_freeze.py --record            # 写入数据库
  python scripts/version_freeze.py --tag v1.0.0        # 建议 tag
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
DB_PATH = BACKEND_DIR / "aimiguard.db"


def _git(cmd: str) -> str:
    """Run git command and return output."""
    try:
        result = subprocess.run(
            f"git {cmd}",
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            shell=True,
            timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def collect_version_info(tag: Optional[str] = None) -> dict:
    """Collect current version information."""
    commit = _git("rev-parse --short HEAD")
    full_commit = _git("rev-parse HEAD")
    branch = _git("rev-parse --abbrev-ref HEAD")
    tags = _git("tag --points-at HEAD")
    dirty = _git("status --porcelain")
    last_tag = _git("describe --tags --abbrev=0 2>nul") or _git("describe --tags --abbrev=0 2>/dev/null")

    return {
        "version": tag or last_tag or "v0.1.0",
        "git_commit": full_commit or "unknown",
        "git_commit_short": commit or "unknown",
        "git_branch": branch or "unknown",
        "git_tags": tags.split("\n") if tags else [],
        "is_dirty": bool(dirty),
        "dirty_files": dirty.split("\n") if dirty else [],
        "schema_version": "1.0.0",
        "deploy_env": os.getenv("DEPLOY_ENV", "dev"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def check_test_readiness() -> dict:
    """Check if Step 10 tests pass."""
    test_files = [
        "tests/test_step10_migration_rehearsal.py",
        "tests/test_step10_load_test.py",
        "tests/test_step10_fault_drill.py",
        "tests/test_step10_canary_slo.py",
    ]

    results = {}
    all_pass = True

    for tf in test_files:
        full_path = PROJECT_ROOT / tf
        if not full_path.exists():
            results[tf] = {"exists": False, "passed": False}
            all_pass = False
            continue

        try:
            proc = subprocess.run(
                f"python -m pytest {tf} -q --tb=no",
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                shell=True,
                timeout=120,
            )
            passed = proc.returncode == 0
            results[tf] = {
                "exists": True,
                "passed": passed,
                "output_tail": proc.stdout.strip().split("\n")[-1] if proc.stdout else "",
            }
            if not passed:
                all_pass = False
        except Exception as exc:
            results[tf] = {"exists": True, "passed": False, "error": str(exc)}
            all_pass = False

    return {"all_pass": all_pass, "tests": results}


def record_release(version_info: dict, db_path: Path) -> int:
    """Record release to release_history table."""
    if not db_path.exists():
        print(f"  ⚠️  数据库不存在: {db_path}")
        return -1

    conn = sqlite3.connect(str(db_path))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        conn.execute(
            "INSERT INTO release_history "
            "(version, git_commit, schema_version, deploy_env, status, deployed_by, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'active', 'version_freeze', ?, ?)",
            (
                version_info["version"],
                version_info["git_commit"],
                version_info["schema_version"],
                version_info["deploy_env"],
                now,
                now,
            ),
        )
        conn.commit()
        release_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return release_id
    except Exception as exc:
        print(f"  ❌ 写入失败: {exc}")
        return -1
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Step 10.6 版本冻结")
    parser.add_argument("--tag", type=str, default=None, help="版本标签（如 v1.0.0）")
    parser.add_argument("--record", action="store_true", help="写入 release_history 表")
    parser.add_argument("--skip-tests", action="store_true", help="跳过测试检查")
    parser.add_argument("--db", type=str, default=None, help="数据库路径")
    args = parser.parse_args()

    print("=" * 60)
    print("  Step 10.6 正式放量上线 · 版本冻结")
    print("=" * 60)

    # 1. Collect version info
    print("\n📋 版本信息收集...")
    info = collect_version_info(tag=args.tag)
    print(f"  版本: {info['version']}")
    print(f"  Commit: {info['git_commit_short']}")
    print(f"  分支: {info['git_branch']}")
    print(f"  环境: {info['deploy_env']}")
    if info["is_dirty"]:
        print(f"  ⚠️  工作区有未提交变更 ({len(info['dirty_files'])} 文件)")

    # 2. Check tests
    if not args.skip_tests:
        print("\n🧪 Step 10 测试检查...")
        test_result = check_test_readiness()
        for tf, res in test_result["tests"].items():
            icon = "✅" if res.get("passed") else "❌"
            tail = res.get("output_tail", "")
            print(f"  {icon} {tf}  {tail}")

        if not test_result["all_pass"]:
            print("\n  ❌ 测试未全部通过，建议修复后再冻结版本")
            if not args.record:
                sys.exit(1)
    else:
        test_result = {"all_pass": "skipped", "tests": {}}
        print("\n  ⏭️  跳过测试检查")

    # 3. Record release
    if args.record:
        db = Path(args.db) if args.db else DB_PATH
        print(f"\n📝 写入发布记录到 {db}...")
        release_id = record_release(info, db)
        if release_id > 0:
            print(f"  ✅ 发布记录已写入 (id={release_id})")
        else:
            print("  ⚠️  发布记录写入失败（数据库可能不存在）")

    # 4. Generate report
    report = {
        "step": "10.6_version_freeze",
        "timestamp": info["timestamp"],
        "version": info,
        "tests": test_result,
        "actions": {
            "recorded": args.record,
            "suggested_tag": args.tag or info["version"],
            "suggested_commands": [
                f'git tag -a {args.tag or info["version"]} -m "Release {args.tag or info["version"]}"',
                f'git push origin {args.tag or info["version"]}',
            ],
        },
    }

    report_path = PROJECT_ROOT / "docs" / "version_freeze_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # 5. Summary
    print("\n" + "=" * 60)
    print("  版本冻结建议")
    print("=" * 60)
    print(f"\n  1. 提交所有变更:")
    print(f'     git add -A && git commit -m "chore: Step 10 预发布与上线完成"')
    print(f"\n  2. 创建版本标签:")
    print(f'     git tag -a {args.tag or info["version"]} -m "Release {args.tag or info["version"]}"')
    print(f"\n  3. 推送标签:")
    print(f'     git push origin {args.tag or info["version"]}')
    print(f"\n  📄 报告已保存: {report_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
