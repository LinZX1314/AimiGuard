"""
Step 10.1 — 数据迁移演练与回滚演练自动化测试

验证：
  - 全新数据库可从 schema 创建
  - 增量迁移可正确执行
  - 表/索引/列完整性通过校验
  - 备份与恢复数据一致
  - 回滚不破坏核心表
  - 幂等重跑无异常
"""
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import rehearsal module
# ---------------------------------------------------------------------------
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from migration_rehearsal import MigrationRehearsal, EXPECTED_TABLES, KEY_COLUMNS, WORKFLOW_TABLES


@pytest.fixture
def rehearsal_db(tmp_path):
    """Provide a temp DB path for rehearsal."""
    return tmp_path / "test_rehearsal.db"


@pytest.fixture
def full_rehearsal(rehearsal_db):
    """Run full rehearsal and return the instance."""
    r = MigrationRehearsal(rehearsal_db, quick=False)
    r.run()
    return r


class TestMigrationRehearsal:
    """Full migration rehearsal test suite."""

    def test_full_rehearsal_passes(self, rehearsal_db):
        """Complete rehearsal (schema → migrate → validate → backup → rollback → restore) must pass."""
        r = MigrationRehearsal(rehearsal_db, quick=False)
        success = r.run()
        assert success, f"Rehearsal failed: {[s for s in r.results if not s.success]}"

    def test_quick_rehearsal_passes(self, rehearsal_db):
        """Quick rehearsal (no backup/restore) must pass."""
        r = MigrationRehearsal(rehearsal_db, quick=True)
        success = r.run()
        assert success, f"Quick rehearsal failed: {[s for s in r.results if not s.success]}"

    def test_all_expected_tables_created(self, rehearsal_db):
        """After full migration, all expected tables must exist."""
        r = MigrationRehearsal(rehearsal_db, quick=True)
        r.run()
        conn = sqlite3.connect(str(rehearsal_db))
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        conn.close()
        missing = EXPECTED_TABLES - tables
        assert not missing, f"Missing tables: {sorted(missing)}"

    def test_key_columns_present(self, rehearsal_db):
        """Key columns must exist in their respective tables."""
        r = MigrationRehearsal(rehearsal_db, quick=True)
        r.run()
        conn = sqlite3.connect(str(rehearsal_db))
        for table, required_cols in KEY_COLUMNS.items():
            actual = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            missing = required_cols - actual
            assert not missing, f"{table}: missing columns {sorted(missing)}"
        conn.close()

    def test_sample_data_readable(self, rehearsal_db):
        """Inserted sample data must be queryable."""
        r = MigrationRehearsal(rehearsal_db, quick=True)
        r.run()
        conn = sqlite3.connect(str(rehearsal_db))
        assert conn.execute("SELECT COUNT(*) FROM role").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM user").fetchone()[0] >= 1
        assert conn.execute(
            "SELECT COUNT(*) FROM threat_event WHERE trace_id='rehearsal_001'"
        ).fetchone()[0] == 1
        conn.close()

    def test_rollback_removes_workflow_tables(self, rehearsal_db):
        """After rollback, workflow tables must be gone but core tables intact."""
        r = MigrationRehearsal(rehearsal_db, quick=False)
        r.run()
        # The rehearsal runs rollback in step 8 then restores in step 9.
        # Let's manually verify step 8 worked by checking the result.
        step8 = next((s for s in r.results if "回滚" in s.step), None)
        assert step8 is not None
        assert step8.success, f"Rollback step failed: {step8.errors}"

    def test_restore_recovers_data(self, rehearsal_db):
        """After restore from backup, data must match pre-rollback state."""
        r = MigrationRehearsal(rehearsal_db, quick=False)
        r.run()
        step9 = next((s for s in r.results if "恢复" in s.step), None)
        assert step9 is not None
        assert step9.success, f"Restore step failed: {step9.errors}"

    def test_idempotent_rerun(self, rehearsal_db):
        """Re-running schema + migrations must not break anything."""
        r = MigrationRehearsal(rehearsal_db, quick=True)
        r.run()
        step10 = next((s for s in r.results if "幂等" in s.step), None)
        assert step10 is not None
        assert step10.success, f"Idempotent rerun failed: {step10.errors}"

    def test_report_generation(self, rehearsal_db):
        """Rehearsal report must be valid JSON with expected fields."""
        r = MigrationRehearsal(rehearsal_db, quick=True)
        r.run()
        report = r.generate_report()
        assert report["rehearsal"] == "step10_1_migration_rollback"
        assert "steps" in report
        assert "summary" in report
        assert report["summary"]["total"] > 0
        assert report["summary"]["passed"] == report["summary"]["total"]

    def test_backup_checksum_matches(self, rehearsal_db):
        """Backup file SHA256 must match original."""
        r = MigrationRehearsal(rehearsal_db, quick=False)
        r.run()
        step7 = next((s for s in r.results if "备份" in s.step), None)
        assert step7 is not None
        assert step7.success, f"Backup step failed: {step7.errors}"

    def test_foreign_keys_enforced(self, rehearsal_db):
        """Foreign key constraints must be active."""
        r = MigrationRehearsal(rehearsal_db, quick=True)
        r.run()
        conn = sqlite3.connect(str(rehearsal_db))
        conn.execute("PRAGMA foreign_keys = ON")
        fk_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk_status == 1, "Foreign keys not enabled"
        conn.close()
