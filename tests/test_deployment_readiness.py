"""
部署就绪验证测试

验证 README 部署文档中引用的所有脚本、配置文件和中间件是否存在且可用：
  1. 备份/恢复脚本功能验证
  2. 生产环境配置模板完备性
  3. IP 白名单中间件
  4. SPA 单包授权服务
  5. 部署架构关键组件
"""
import importlib
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


# ---------------------------------------------------------------------------
# 1. 备份/恢复脚本
# ---------------------------------------------------------------------------

class TestBackupRestore:
    """备份与恢复脚本验证"""

    def test_backup_script_exists(self):
        assert (SCRIPTS_DIR / "backup_db.py").exists()

    def test_restore_script_exists(self):
        assert (SCRIPTS_DIR / "restore_db.py").exists()

    def test_backup_creates_valid_copy(self, tmp_path):
        """备份脚本应能创建有效的数据库副本"""
        sys.path.insert(0, str(SCRIPTS_DIR))
        from backup_db import backup_database

        # 创建临时源数据库
        src_db = tmp_path / "source.db"
        conn = sqlite3.connect(str(src_db))
        conn.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO test_data VALUES (1, 'hello')")
        conn.commit()
        conn.close()

        backup_dir = tmp_path / "backups"
        result = backup_database(src_db, backup_dir)

        assert result["success"] is True
        assert Path(result["backup_file"]).exists()
        assert result["file_size"] > 0
        assert len(result["backup_checksum"]) == 64  # SHA256

        # 验证备份数据可读
        backup_conn = sqlite3.connect(result["backup_file"])
        row = backup_conn.execute("SELECT value FROM test_data WHERE id=1").fetchone()
        backup_conn.close()
        assert row[0] == "hello"

    def test_backup_with_compression(self, tmp_path):
        """压缩备份应生成 .gz 文件"""
        sys.path.insert(0, str(SCRIPTS_DIR))
        from backup_db import backup_database

        src_db = tmp_path / "source.db"
        conn = sqlite3.connect(str(src_db))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        result = backup_database(src_db, tmp_path / "bk", compress=True)
        assert result["success"] is True
        assert result["compressed"] is True
        assert result["backup_file"].endswith(".gz")

    def test_backup_nonexistent_db(self, tmp_path):
        sys.path.insert(0, str(SCRIPTS_DIR))
        from backup_db import backup_database

        result = backup_database(tmp_path / "no_such.db", tmp_path / "bk")
        assert result["success"] is False

    def test_restore_verify_backup(self, tmp_path):
        """恢复脚本应能验证备份完整性"""
        sys.path.insert(0, str(SCRIPTS_DIR))
        from restore_db import verify_backup

        # 创建有效备份
        db_path = tmp_path / "valid.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        ok, reason = verify_backup(db_path)
        assert ok is True
        assert reason == "ok"

    def test_restore_reject_invalid(self, tmp_path):
        """恢复脚本应拒绝损坏的备份"""
        sys.path.insert(0, str(SCRIPTS_DIR))
        from restore_db import verify_backup

        bad_path = tmp_path / "corrupt.db"
        bad_path.write_bytes(b"this is not a database")

        ok, reason = verify_backup(bad_path)
        assert ok is False

    def test_restore_creates_safety_backup(self, tmp_path):
        """恢复时应自动备份当前数据库"""
        sys.path.insert(0, str(SCRIPTS_DIR))
        from restore_db import restore_database

        # 创建"当前数据库"
        current_db = tmp_path / "current.db"
        conn = sqlite3.connect(str(current_db))
        conn.execute("CREATE TABLE old_data (x TEXT)")
        conn.execute("INSERT INTO old_data VALUES ('original')")
        conn.commit()
        conn.close()

        # 创建备份源
        backup_db = tmp_path / "backup.db"
        conn2 = sqlite3.connect(str(backup_db))
        conn2.execute("CREATE TABLE new_data (y TEXT)")
        conn2.execute("INSERT INTO new_data VALUES ('restored')")
        conn2.commit()
        conn2.close()

        result = restore_database(backup_db, current_db)
        assert result["success"] is True

        # 安全备份应存在
        safety_files = list(tmp_path.glob("current_pre_restore_*.db"))
        assert len(safety_files) >= 1

        # 恢复后的数据应是新数据
        conn3 = sqlite3.connect(str(current_db))
        row = conn3.execute("SELECT y FROM new_data").fetchone()
        conn3.close()
        assert row[0] == "restored"

    def test_backup_list(self, tmp_path):
        """列出备份应返回正确结果"""
        sys.path.insert(0, str(SCRIPTS_DIR))
        from backup_db import backup_database, list_backups

        src = tmp_path / "src.db"
        conn = sqlite3.connect(str(src))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        bk_dir = tmp_path / "bk"
        backup_database(src, bk_dir, label="test1")
        backup_database(src, bk_dir, label="test2")

        backups = list_backups(bk_dir)
        assert len(backups) >= 2

    def test_cleanup_old_backups(self, tmp_path):
        sys.path.insert(0, str(SCRIPTS_DIR))
        from backup_db import cleanup_old_backups

        bk_dir = tmp_path / "bk"
        bk_dir.mkdir()
        # 创建一个"旧"备份文件
        old_file = bk_dir / "aimiguard_20200101_000000.db"
        old_file.write_text("old")
        # 设置修改时间为很久以前
        os.utime(old_file, (0, 0))

        removed = cleanup_old_backups(bk_dir, retain_days=1)
        assert len(removed) >= 1
        assert not old_file.exists()


# ---------------------------------------------------------------------------
# 2. 生产环境配置
# ---------------------------------------------------------------------------

class TestProductionConfig:
    """生产环境配置模板验证"""

    def test_env_prod_exists(self):
        assert (BACKEND_DIR / ".env.prod").exists()

    def test_env_prod_has_required_vars(self):
        content = (BACKEND_DIR / ".env.prod").read_text(encoding="utf-8")
        required = [
            "APP_ENV", "DEBUG", "DATABASE_URL", "JWT_SECRET",
            "JWT_EXPIRE_MINUTES", "LLM_PROVIDER", "LLM_BASE_URL",
            "AUDIT_ENABLED", "LOG_LEVEL", "MAX_WORKERS",
        ]
        for var in required:
            assert var in content, f".env.prod missing {var}"

    def test_env_prod_debug_false(self):
        content = (BACKEND_DIR / ".env.prod").read_text(encoding="utf-8")
        assert "DEBUG=false" in content, "Production must have DEBUG=false"

    def test_frontend_env_production_exists(self):
        assert (PROJECT_ROOT / "frontend" / ".env.production").exists()

    def test_frontend_env_has_vite_vars(self):
        content = (PROJECT_ROOT / "frontend" / ".env.production").read_text(encoding="utf-8")
        assert "VITE_API_BASE_URL" in content
        assert "VITE_APP_TITLE" in content

    def test_env_example_exists(self):
        assert (BACKEND_DIR / ".env.example").exists()


# ---------------------------------------------------------------------------
# 3. IP 白名单中间件
# ---------------------------------------------------------------------------

class TestIPWhitelist:
    """IP 白名单中间件验证"""

    def test_middleware_module_exists(self):
        assert (BACKEND_DIR / "middleware" / "ip_whitelist.py").exists()

    def test_middleware_importable(self):
        from middleware.ip_whitelist import IPWhitelistMiddleware
        assert IPWhitelistMiddleware is not None

    def test_whitelisted_ip_allowed(self):
        from middleware.ip_whitelist import IPWhitelistMiddleware
        mw = IPWhitelistMiddleware(app=None, whitelist=["10.0.0.0/8"])
        assert mw._is_whitelisted("10.1.2.3") is True
        assert mw._is_whitelisted("192.168.1.1") is False

    def test_empty_whitelist_disables_filter(self):
        from middleware.ip_whitelist import IPWhitelistMiddleware
        mw = IPWhitelistMiddleware(app=None, whitelist=[])
        assert mw.enabled is False

    def test_multiple_networks(self):
        from middleware.ip_whitelist import IPWhitelistMiddleware
        mw = IPWhitelistMiddleware(
            app=None,
            whitelist=["10.0.0.0/8", "192.168.0.0/16", "172.16.0.0/12"],
        )
        assert mw._is_whitelisted("10.1.1.1") is True
        assert mw._is_whitelisted("192.168.1.1") is True
        assert mw._is_whitelisted("172.20.0.1") is True
        assert mw._is_whitelisted("8.8.8.8") is False

    def test_single_ip_whitelist(self):
        from middleware.ip_whitelist import IPWhitelistMiddleware
        mw = IPWhitelistMiddleware(app=None, whitelist=["198.51.100.10/32"])
        assert mw._is_whitelisted("198.51.100.10") is True
        assert mw._is_whitelisted("198.51.100.11") is False

    def test_invalid_ip_rejected(self):
        from middleware.ip_whitelist import IPWhitelistMiddleware
        mw = IPWhitelistMiddleware(app=None, whitelist=["10.0.0.0/8"])
        assert mw._is_whitelisted("not-an-ip") is False


# ---------------------------------------------------------------------------
# 4. SPA 单包授权
# ---------------------------------------------------------------------------

class TestSPAService:
    """SPA 单包授权服务验证"""

    def test_spa_module_exists(self):
        assert (BACKEND_DIR / "services" / "spa_service.py").exists()

    def test_generate_and_verify_token(self):
        from services.spa_service import generate_spa_token, verify_spa_token

        secret = "test-secret-key-32chars-minimum!!"
        ip = "10.0.0.1"
        token = generate_spa_token(ip, secret)

        ok, reason = verify_spa_token(token, ip, secret)
        assert ok is True
        assert reason == "ok"

    def test_wrong_ip_rejected(self):
        from services.spa_service import generate_spa_token, verify_spa_token

        secret = "test-secret"
        token = generate_spa_token("10.0.0.1", secret)
        ok, reason = verify_spa_token(token, "10.0.0.2", secret)
        assert ok is False
        assert reason == "ip_mismatch"

    def test_wrong_secret_rejected(self):
        from services.spa_service import generate_spa_token, verify_spa_token

        token = generate_spa_token("10.0.0.1", "secret-a")
        ok, reason = verify_spa_token(token, "10.0.0.1", "secret-b")
        assert ok is False
        assert reason == "signature_mismatch"

    def test_expired_token_rejected(self):
        from services.spa_service import verify_spa_token
        import hmac as hmac_mod
        import hashlib
        import time

        secret = "test-secret"
        ip = "10.0.0.1"
        old_ts = int(time.time()) - 600  # 10 minutes ago
        message = f"{ip}:{old_ts}"
        sig = hmac_mod.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        old_token = f"{message}:{sig}"

        ok, reason = verify_spa_token(old_token, ip, secret, ttl=300)
        assert ok is False
        assert reason == "token_expired"

    def test_empty_token_rejected(self):
        from services.spa_service import verify_spa_token
        ok, reason = verify_spa_token("", "10.0.0.1", "secret")
        assert ok is False

    def test_malformed_token_rejected(self):
        from services.spa_service import verify_spa_token
        ok, reason = verify_spa_token("garbage-token", "10.0.0.1", "secret")
        assert ok is False


# ---------------------------------------------------------------------------
# 5. 部署架构关键组件
# ---------------------------------------------------------------------------

class TestDeploymentComponents:
    """部署架构核心组件验证"""

    def test_main_entry_exists(self):
        assert (BACKEND_DIR / "main.py").exists()

    def test_init_db_exists(self):
        assert (BACKEND_DIR / "init_db.py").exists()

    def test_requirements_exists(self):
        assert (BACKEND_DIR / "requirements.txt").exists()

    def test_frontend_package_json_exists(self):
        assert (PROJECT_ROOT / "frontend" / "package.json").exists()

    def test_frontend_index_html_exists(self):
        assert (PROJECT_ROOT / "frontend" / "index.html").exists()

    def test_dev_script_exists(self):
        assert (SCRIPTS_DIR / "dev.ps1").exists()

    def test_ci_workflow_exists(self):
        assert (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").exists()

    def test_schema_sql_exists(self):
        assert (PROJECT_ROOT / "sql" / "mvp_schema.sql").exists()

    def test_gitignore_exists(self):
        assert (PROJECT_ROOT / ".gitignore").exists()

    def test_quickstart_exists(self):
        assert (PROJECT_ROOT / "QUICKSTART.md").exists()
