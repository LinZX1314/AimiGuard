"""
蜜罐策略管理服务层测试

覆盖 services/honeypot_manager.py：
  1. create_honeypot — 创建蜜罐配置
  2. list_honeypots — 查询/过滤/分页
  3. get_honeypot — 获取详情
  4. update_honeypot — 更新配置与状态
  5. update_honeytoken — 更新蜜标状态
  6. 参数校验（无效类型/状态）
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from services.honeypot_manager import HoneypotManager


class TestCreateHoneypot:

    def test_create_success(self, db):
        hp = HoneypotManager.create_honeypot(
            db,
            name="test-ssh-pot",
            honeypot_type="ssh",
            target_service="22/tcp",
            bait_data="root:toor",
            trace_id="test_create",
        )
        assert hp.id is not None
        assert hp.name == "test-ssh-pot"
        assert hp.type == "ssh"
        assert hp.status == "INACTIVE"

    def test_create_invalid_type(self, db):
        with pytest.raises(ValueError, match="Invalid type"):
            HoneypotManager.create_honeypot(
                db, name="bad", honeypot_type="invalid_type"
            )

    def test_create_minimal(self, db):
        hp = HoneypotManager.create_honeypot(
            db, name="minimal-pot", honeypot_type="http"
        )
        assert hp.id is not None
        assert hp.target_service is None


class TestListHoneypots:

    def test_list_all(self, db):
        result = HoneypotManager.list_honeypots(db)
        assert "total" in result
        assert "items" in result
        assert isinstance(result["items"], list)

    def test_filter_by_type(self, db):
        HoneypotManager.create_honeypot(db, name="redis-pot", honeypot_type="redis")
        result = HoneypotManager.list_honeypots(db, honeypot_type="redis")
        for item in result["items"]:
            assert item.type == "redis"

    def test_pagination(self, db):
        for i in range(5):
            HoneypotManager.create_honeypot(
                db, name=f"page-pot-{i}", honeypot_type="http"
            )
        result = HoneypotManager.list_honeypots(db, page=1, page_size=2)
        assert len(result["items"]) <= 2
        assert result["page"] == 1


class TestGetHoneypot:

    def test_get_existing(self, db):
        hp = HoneypotManager.create_honeypot(db, name="get-test", honeypot_type="ftp")
        found = HoneypotManager.get_honeypot(db, hp.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_nonexistent(self, db):
        assert HoneypotManager.get_honeypot(db, 99999) is None


class TestUpdateHoneypot:

    def test_update_name(self, db):
        hp = HoneypotManager.create_honeypot(db, name="old-name", honeypot_type="ssh")
        updated = HoneypotManager.update_honeypot(db, hp.id, name="new-name")
        assert updated.name == "new-name"

    def test_update_status(self, db):
        hp = HoneypotManager.create_honeypot(db, name="status-test", honeypot_type="http")
        updated = HoneypotManager.update_honeypot(db, hp.id, status="ACTIVE")
        assert updated.status == "ACTIVE"

    def test_update_nonexistent(self, db):
        assert HoneypotManager.update_honeypot(db, 99999, name="x") is None

    def test_update_invalid_status_ignored(self, db):
        hp = HoneypotManager.create_honeypot(db, name="inv-status", honeypot_type="ssh")
        updated = HoneypotManager.update_honeypot(db, hp.id, status="BOGUS")
        assert updated.status == "INACTIVE"  # unchanged


class TestUpdateHoneytoken:

    def test_update_nonexistent(self, db):
        assert HoneypotManager.update_honeytoken(db, 99999, status="expired") is None

    def test_invalid_status_rejected(self, db):
        with pytest.raises(ValueError, match="Invalid status"):
            HoneypotManager.update_honeytoken(db, 1, status="bogus")
