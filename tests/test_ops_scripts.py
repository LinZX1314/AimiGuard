"""
运维脚本测试

验证 README 故障恢复章节引用的运维脚本功能：
  1. cleanup_old_backups.py — 过期备份清理
  2. archive_old_data.py — 历史数据归档
  3. optimize_db.py — 数据库优化
  4. check_queue_depth.py — 队列堆积检查
"""
import os
import sqlite3
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


# ---------------------------------------------------------------------------
# 1. 过期备份清理
# ---------------------------------------------------------------------------

class TestCleanupOldBackups:

    def test_script_exists(self):
        assert (SCRIPTS_DIR / "cleanup_old_backups.py").exists()

    def test_cleanup_removes_old_files(self, tmp_path):
        from cleanup_old_backups import cleanup_old_backups

        bk_dir = tmp_path / "backups"
        bk_dir.mkdir()

        # 创建"旧"文件
        old = bk_dir / "aimiguard_20200101_000000.db"
        old.write_text("old-backup-data")
        os.utime(old, (0, 0))

        # 创建"新"文件
        new = bk_dir / "aimiguard_20991231_235959.db"
        new.write_text("new-backup-data")

        result = cleanup_old_backups(bk_dir, retain_days=1)
        assert len(result["removed"]) == 1
        assert "aimiguard_20200101" in result["removed"][0]
        assert not old.exists()
        assert new.exists()

    def test_dry_run_no_delete(self, tmp_path):
        from cleanup_old_backups import cleanup_old_backups

        bk_dir = tmp_path / "backups"
        bk_dir.mkdir()
        old = bk_dir / "aimiguard_20200101_000000.db"
        old.write_text("data")
        os.utime(old, (0, 0))

        result = cleanup_old_backups(bk_dir, retain_days=1, dry_run=True)
        assert len(result["removed"]) == 1
        assert old.exists()  # 不应删除

    def test_empty_dir(self, tmp_path):
        from cleanup_old_backups import cleanup_old_backups

        bk_dir = tmp_path / "backups"
        bk_dir.mkdir()
        result = cleanup_old_backups(bk_dir, retain_days=1)
        assert len(result["removed"]) == 0

    def test_nonexistent_dir(self, tmp_path):
        from cleanup_old_backups import cleanup_old_backups

        result = cleanup_old_backups(tmp_path / "no_such_dir")
        assert result["freed_bytes"] == 0


# ---------------------------------------------------------------------------
# 2. 历史数据归档
# ---------------------------------------------------------------------------

class TestArchiveOldData:

    def test_script_exists(self):
        assert (SCRIPTS_DIR / "archive_old_data.py").exists()

    def test_archive_moves_old_records(self, tmp_path):
        from archive_old_data import archive_old_data

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE audit_log (id INTEGER PRIMARY KEY, actor TEXT, action TEXT, target TEXT, result TEXT, trace_id TEXT, created_at TEXT)")
        # 插入旧记录
        conn.execute("INSERT INTO audit_log VALUES (1,'admin','login','system','ok','t1','2020-01-01 00:00:00')")
        # 插入新记录
        conn.execute("INSERT INTO audit_log VALUES (2,'admin','login','system','ok','t2','2099-01-01 00:00:00')")
        conn.commit()
        conn.close()

        archive_dir = tmp_path / "archives"
        result = archive_old_data(db_path, archive_dir, days=1, purge=True)

        assert result["success"] is True
        assert result["total_rows"] == 1
        assert "audit_log" in result["tables"]

        # 源表应只剩新记录
        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        conn.close()
        assert count == 1

    def test_archive_dry_run(self, tmp_path):
        from archive_old_data import archive_old_data

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE audit_log (id INTEGER PRIMARY KEY, actor TEXT, action TEXT, target TEXT, result TEXT, trace_id TEXT, created_at TEXT)")
        conn.execute("INSERT INTO audit_log VALUES (1,'a','b','c','d','e','2020-01-01 00:00:00')")
        conn.commit()
        conn.close()

        result = archive_old_data(db_path, tmp_path / "arch", days=1, dry_run=True)
        assert result["total_rows"] == 1
        assert result["dry_run"] is True

        # 源数据应保留
        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        conn.close()
        assert count == 1

    def test_no_old_data(self, tmp_path):
        from archive_old_data import archive_old_data

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE audit_log (id INTEGER PRIMARY KEY, actor TEXT, action TEXT, target TEXT, result TEXT, trace_id TEXT, created_at TEXT)")
        conn.execute("INSERT INTO audit_log VALUES (1,'a','b','c','d','e','2099-01-01 00:00:00')")
        conn.commit()
        conn.close()

        result = archive_old_data(db_path, tmp_path / "arch", days=1)
        assert result["total_rows"] == 0

    def test_nonexistent_db(self, tmp_path):
        from archive_old_data import archive_old_data

        result = archive_old_data(tmp_path / "nope.db", tmp_path / "arch")
        assert result["success"] is False


# ---------------------------------------------------------------------------
# 3. 数据库优化
# ---------------------------------------------------------------------------

class TestOptimizeDb:

    def test_script_exists(self):
        assert (SCRIPTS_DIR / "optimize_db.py").exists()

    def test_optimize_healthy_db(self, tmp_path):
        from optimize_db import optimize_database

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t1 (id INTEGER PRIMARY KEY, data TEXT)")
        for i in range(100):
            conn.execute("INSERT INTO t1 VALUES (?, ?)", (i, f"data_{i}"))
        conn.commit()
        conn.close()

        result = optimize_database(db_path)
        assert result["success"] is True
        assert result["table_count"] >= 1
        assert result["total_rows"] >= 100

    def test_optimize_skip_vacuum(self, tmp_path):
        from optimize_db import optimize_database

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t1 (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        result = optimize_database(db_path, skip_vacuum=True)
        assert result["success"] is True

    def test_nonexistent_db(self, tmp_path):
        from optimize_db import optimize_database

        result = optimize_database(tmp_path / "nope.db")
        assert result["success"] is False

    def test_table_stats(self, tmp_path):
        from optimize_db import get_table_stats

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE alpha (id INTEGER)")
        conn.execute("CREATE TABLE beta (id INTEGER)")
        conn.execute("INSERT INTO alpha VALUES (1)")
        conn.execute("INSERT INTO beta VALUES (1)")
        conn.execute("INSERT INTO beta VALUES (2)")
        conn.commit()

        stats = get_table_stats(conn)
        conn.close()

        by_name = {s["table"]: s["rows"] for s in stats}
        assert by_name["alpha"] == 1
        assert by_name["beta"] == 2


# ---------------------------------------------------------------------------
# 4. 队列堆积检查
# ---------------------------------------------------------------------------

class TestCheckQueueDepth:

    def test_script_exists(self):
        assert (SCRIPTS_DIR / "check_queue_depth.py").exists()

    def test_empty_queues_ok(self, tmp_path):
        from check_queue_depth import check_all_queues

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE execution_task (id INTEGER PRIMARY KEY, status TEXT)")
        conn.execute("CREATE TABLE scan_task (id INTEGER PRIMARY KEY, status TEXT)")
        conn.execute("CREATE TABLE firewall_sync_task (id INTEGER PRIMARY KEY, status TEXT)")
        conn.commit()
        conn.close()

        result = check_all_queues(db_path)
        assert result["success"] is True
        assert result["overall_level"] == "ok"

    def test_pending_tasks_detected(self, tmp_path):
        from check_queue_depth import check_all_queues

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE execution_task (id INTEGER PRIMARY KEY, status TEXT)")
        conn.execute("CREATE TABLE scan_task (id INTEGER PRIMARY KEY, status TEXT)")
        conn.execute("CREATE TABLE firewall_sync_task (id INTEGER PRIMARY KEY, status TEXT)")
        for i in range(10):
            conn.execute("INSERT INTO execution_task VALUES (?, 'pending')", (i,))
        conn.commit()
        conn.close()

        result = check_all_queues(db_path)
        assert result["success"] is True
        et = [q for q in result["queues"] if q["queue"] == "execution_task"][0]
        assert et["pending"] == 10

    def test_missing_tables_handled(self, tmp_path):
        from check_queue_depth import check_all_queues

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.commit()
        conn.close()

        result = check_all_queues(db_path)
        assert result["success"] is True
        for q in result["queues"]:
            assert q["exists"] is False

    def test_nonexistent_db(self, tmp_path):
        from check_queue_depth import check_all_queues

        result = check_all_queues(tmp_path / "nope.db")
        assert result["success"] is False

    def test_critical_threshold(self, tmp_path):
        from check_queue_depth import check_all_queues

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE execution_task (id INTEGER PRIMARY KEY, status TEXT)")
        conn.execute("CREATE TABLE scan_task (id INTEGER PRIMARY KEY, status TEXT)")
        conn.execute("CREATE TABLE firewall_sync_task (id INTEGER PRIMARY KEY, status TEXT)")
        # 插入大量待处理任务
        for i in range(250):
            conn.execute("INSERT INTO execution_task VALUES (?, 'pending')", (i,))
        conn.commit()
        conn.close()

        result = check_all_queues(db_path)
        assert result["overall_level"] == "critical"
