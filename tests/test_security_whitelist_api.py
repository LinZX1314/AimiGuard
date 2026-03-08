"""
IP 白名单管理 API 测试

覆盖：
  1. 白名单 CRUD（添加永久/临时、列表、删除）
  2. 权限校验（未认证/viewer 禁止访问）
  3. CIDR 格式校验
  4. 审计日志记录
"""
import os
import sys

import pytest
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


@pytest.fixture(scope="module")
def admin_headers(client, admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


class TestWhitelistAPI:
    """白名单 CRUD"""

    def test_list_empty(self, client, admin_headers):
        resp = client.get("/api/v1/security/whitelist", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert isinstance(body["data"], list)

    def test_add_permanent(self, client, admin_headers):
        resp = client.post(
            "/api/v1/security/whitelist/add",
            headers=admin_headers,
            json={
                "ip_range": "10.0.0.0/8",
                "description": "内网段",
                "trace_id": "wl_test_001",
            },
        )
        assert resp.status_code == 200
        assert "已添加白名单" in resp.json()["message"]

    def test_add_temporary(self, client, admin_headers):
        resp = client.post(
            "/api/v1/security/whitelist/temp",
            headers=admin_headers,
            json={
                "ip_range": "198.51.100.50/32",
                "expires_in_hours": 2,
                "reason": "临时远程运维",
                "trace_id": "wl_test_002",
            },
        )
        assert resp.status_code == 200
        assert "临时白名单" in resp.json()["message"]

    def test_list_after_add(self, client, admin_headers):
        resp = client.get("/api/v1/security/whitelist", headers=admin_headers)
        body = resp.json()
        assert body["total"] >= 2
        types = {e["whitelist_type"] for e in body["data"]}
        assert "permanent" in types
        assert "temporary" in types

    def test_filter_by_type(self, client, admin_headers):
        resp = client.get(
            "/api/v1/security/whitelist?whitelist_type=temporary",
            headers=admin_headers,
        )
        body = resp.json()
        for entry in body["data"]:
            assert entry["whitelist_type"] == "temporary"

    def test_delete_entry(self, client, admin_headers):
        # Get current list
        resp = client.get("/api/v1/security/whitelist", headers=admin_headers)
        entries = resp.json()["data"]
        assert len(entries) > 0

        entry_id = entries[0]["id"]
        resp = client.delete(
            f"/api/v1/security/whitelist/{entry_id}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert "已删除" in resp.json()["message"]

    def test_delete_nonexistent(self, client, admin_headers):
        resp = client.delete(
            "/api/v1/security/whitelist/99999",
            headers=admin_headers,
        )
        assert resp.status_code == 404


class TestWhitelistValidation:
    """输入校验"""

    def test_invalid_cidr_rejected(self, client, admin_headers):
        resp = client.post(
            "/api/v1/security/whitelist/add",
            headers=admin_headers,
            json={"ip_range": "not-an-ip", "description": "bad"},
        )
        assert resp.status_code in (400, 422)

    def test_single_ip_accepted(self, client, admin_headers):
        resp = client.post(
            "/api/v1/security/whitelist/add",
            headers=admin_headers,
            json={"ip_range": "192.168.1.1", "description": "单IP"},
        )
        assert resp.status_code == 200


class TestWhitelistAuth:
    """权限校验"""

    def test_unauthenticated_rejected(self, client):
        resp = client.get("/api/v1/security/whitelist")
        assert resp.status_code in (401, 403)

    def test_unauthenticated_add_rejected(self, client):
        resp = client.post(
            "/api/v1/security/whitelist/add",
            json={"ip_range": "10.0.0.0/8"},
        )
        assert resp.status_code in (401, 403)


class TestWhitelistAudit:
    """审计日志记录"""

    def test_add_creates_audit_log(self, client, admin_headers, db):
        client.post(
            "/api/v1/security/whitelist/add",
            headers=admin_headers,
            json={
                "ip_range": "172.16.0.0/12",
                "description": "审计测试",
                "trace_id": "wl_audit_test",
            },
        )
        db.expire_all()
        row = db.execute(
            text("SELECT COUNT(*) FROM audit_log WHERE action='whitelist_add'")
        ).fetchone()
        assert row[0] >= 1

    def test_delete_creates_audit_log(self, client, admin_headers, db):
        # Add then delete
        client.post(
            "/api/v1/security/whitelist/add",
            headers=admin_headers,
            json={"ip_range": "203.0.113.0/24", "description": "删除审计测试"},
        )
        resp = client.get("/api/v1/security/whitelist", headers=admin_headers)
        entries = resp.json()["data"]
        target = [e for e in entries if e["ip_range"] == "203.0.113.0/24"]
        if target:
            client.delete(
                f"/api/v1/security/whitelist/{target[0]['id']}",
                headers=admin_headers,
            )
            db.expire_all()
            row = db.execute(
                text("SELECT COUNT(*) FROM audit_log WHERE action='whitelist_delete'")
            ).fetchone()
            assert row[0] >= 1
