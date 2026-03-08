"""D2-01 蜜罐策略管理 测试"""
import pytest
from starlette.testclient import TestClient


def _create_honeypot(client: TestClient, token: str, **kwargs) -> dict:
    defaults = {"name": "SSH蜜罐", "type": "ssh"}
    defaults.update(kwargs)
    res = client.post(
        "/api/v1/honeypots",
        json=defaults,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    return res.json().get("data") or res.json()


# ── 创建 ──

def test_create_honeypot(client: TestClient, admin_token: str):
    data = _create_honeypot(client, admin_token)
    assert data["name"] == "SSH蜜罐"
    assert data["type"] == "ssh"
    assert data["status"] == "INACTIVE"
    assert data["id"] is not None


def test_create_honeypot_custom(client: TestClient, admin_token: str):
    data = _create_honeypot(client, admin_token, name="自定义蜜罐", type="custom", bait_data="fake-api-key")
    assert data["type"] == "custom"
    assert data["bait_data"] == "fake-api-key"


# ── 列表查询 ──

def test_list_honeypots_empty(client: TestClient, admin_token: str):
    res = client.get("/api/v1/honeypots", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["total"] == 0


def test_list_honeypots_filter_type(client: TestClient, admin_token: str):
    _create_honeypot(client, admin_token, name="SSH1", type="ssh")
    _create_honeypot(client, admin_token, name="HTTP1", type="http")
    res = client.get("/api/v1/honeypots?type=ssh", headers={"Authorization": f"Bearer {admin_token}"})
    data = res.json().get("data") or res.json()
    assert data["total"] == 1
    assert data["items"][0]["type"] == "ssh"


# ── 详情 ──

def test_get_honeypot_detail(client: TestClient, admin_token: str):
    hp = _create_honeypot(client, admin_token)
    res = client.get(f"/api/v1/honeypots/{hp['id']}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["id"] == hp["id"]


def test_get_honeypot_not_found(client: TestClient, admin_token: str):
    res = client.get("/api/v1/honeypots/99999", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 404


# ── 更新 ──

def test_update_honeypot_status(client: TestClient, admin_token: str):
    hp = _create_honeypot(client, admin_token)
    res = client.put(
        f"/api/v1/honeypots/{hp['id']}",
        json={"status": "ACTIVE"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["status"] == "ACTIVE"


def test_update_honeypot_name(client: TestClient, admin_token: str):
    hp = _create_honeypot(client, admin_token)
    res = client.put(
        f"/api/v1/honeypots/{hp['id']}",
        json={"name": "SSH蜜罐-改名"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["name"] == "SSH蜜罐-改名"


# ── 告警关联 ──

def test_honeypot_alerts_empty(client: TestClient, admin_token: str):
    hp = _create_honeypot(client, admin_token)
    res = client.get(
        f"/api/v1/honeypots/{hp['id']}/alerts",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["total"] >= 0
