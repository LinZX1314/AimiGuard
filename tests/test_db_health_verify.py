"""
数据库健康检查与验证脚本测试

覆盖：
  1. check_db_health.py — 健康检查（完整性/页面/表统计/RBAC/评分）
  2. verify_db.py — 结构验证（表存在性/RBAC完整性/索引/外键）
"""
import importlib.util
import os
import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def _load_script(name: str):
    """从 scripts/ 显式加载模块，避免与 backend/ 同名模块冲突"""
    spec = importlib.util.spec_from_file_location(f"scripts_{name}", SCRIPTS_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# 1. check_db_health.py
# ---------------------------------------------------------------------------

class TestCheckDbHealth:

    def test_script_exists(self):
        assert (SCRIPTS_DIR / "check_db_health.py").exists()

    def test_healthy_db(self, tmp_path):
        check_health = _load_script("check_db_health").check_health

        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE user (id INTEGER PRIMARY KEY, username TEXT)")
        conn.execute("CREATE TABLE role (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("CREATE TABLE permission (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO user VALUES (1, 'admin')")
        conn.execute("INSERT INTO role VALUES (1, 'admin')")
        conn.execute("INSERT INTO permission VALUES (1, 'view')")
        conn.commit()
        conn.close()

        report = check_health(db)
        assert report["healthy"] is True
        assert report["checks"]["integrity"]["ok"] is True
        assert report["total_tables"] >= 3
        assert report["health_score"] > 0

    def test_nonexistent_db(self, tmp_path):
        check_health = _load_script("check_db_health").check_health

        report = check_health(tmp_path / "nope.db")
        assert report["healthy"] is False
        assert not report["exists"]

    def test_file_size_reported(self, tmp_path):
        check_health = _load_script("check_db_health").check_health

        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        report = check_health(db)
        assert report["file_size_bytes"] > 0
        assert report["file_size_mb"] >= 0

    def test_page_stats(self, tmp_path):
        check_health = _load_script("check_db_health").check_health

        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        report = check_health(db)
        pages = report["checks"]["pages"]
        assert "page_count" in pages
        assert "page_size" in pages
        assert "fragmentation_pct" in pages

    def test_rbac_warning_when_empty(self, tmp_path):
        check_health = _load_script("check_db_health").check_health

        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE user (id INTEGER PRIMARY KEY, username TEXT)")
        conn.execute("CREATE TABLE role (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("CREATE TABLE permission (id INTEGER PRIMARY KEY, name TEXT)")
        conn.commit()
        conn.close()

        report = check_health(db)
        assert any("无用户" in w for w in report["warnings"])


# ---------------------------------------------------------------------------
# 2. verify_db.py (scripts/)
# ---------------------------------------------------------------------------

class TestVerifyDb:

    def test_script_exists(self):
        assert (SCRIPTS_DIR / "verify_db.py").exists()

    def test_valid_db(self, tmp_path):
        _mod = _load_script("verify_db")
        verify_database = _mod.verify_database
        REQUIRED_TABLES = _mod.REQUIRED_TABLES

        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        for table in REQUIRED_TABLES:
            conn.execute(f"CREATE TABLE IF NOT EXISTS [{table}] (id INTEGER PRIMARY KEY)")

        # 插入 RBAC 数据
        conn.execute("INSERT INTO user VALUES (1)")
        conn.execute("INSERT INTO role VALUES (1)")
        conn.execute("INSERT INTO permission VALUES (1)")
        conn.execute("INSERT INTO user_role VALUES (1)")
        conn.execute("INSERT INTO role_permission VALUES (1)")
        conn.commit()
        conn.close()

        report = verify_database(db)
        assert report["tables_found"] >= len(REQUIRED_TABLES)
        assert len(report["tables_missing"]) == 0

    def test_missing_tables_detected(self, tmp_path):
        verify_database = _load_script("verify_db").verify_database

        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE user (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE role (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE permission (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO role VALUES (1)")
        conn.execute("INSERT INTO permission VALUES (1)")
        conn.commit()
        conn.close()

        report = verify_database(db)
        assert len(report["tables_missing"]) > 0

    def test_nonexistent_db(self, tmp_path):
        verify_database = _load_script("verify_db").verify_database

        report = verify_database(tmp_path / "nope.db")
        assert report["valid"] is False

    def test_empty_rbac_flagged(self, tmp_path):
        _mod = _load_script("verify_db")
        verify_database = _mod.verify_database
        REQUIRED_TABLES = _mod.REQUIRED_TABLES

        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        for table in REQUIRED_TABLES:
            conn.execute(f"CREATE TABLE IF NOT EXISTS [{table}] (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        report = verify_database(db)
        assert report["valid"] is False  # 无 role/permission 数据

    def test_index_count(self, tmp_path):
        verify_database = _load_script("verify_db").verify_database

        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        conn.execute("CREATE INDEX idx_t_val ON t(val)")
        conn.commit()
        conn.close()

        report = verify_database(db)
        assert report["indexes"] >= 1
