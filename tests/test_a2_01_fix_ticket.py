"""A2-01 漏洞修复工单 测试"""
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session as SASession
from sqlalchemy import text


# ── 创建工单 ──

def test_create_ticket(client: TestClient, admin_token: str):
    """创建修复工单应返回工单信息"""
    res = client.post(
        "/api/v1/fix-tickets",
        json={"priority": "high", "assignee": "zhangsan"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["priority"] == "high"
    assert data["assignee"] == "zhangsan"
    assert data["status"] == "OPEN"
    assert data["id"] is not None


def test_create_ticket_default_priority(client: TestClient, admin_token: str):
    """不指定优先级应默认 medium"""
    res = client.post(
        "/api/v1/fix-tickets",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["priority"] == "medium"
    assert data["status"] == "OPEN"


# ── 查询工单 ──

def test_list_tickets_empty(client: TestClient, admin_token: str):
    """无工单时应返回空列表"""
    res = client.get(
        "/api/v1/fix-tickets",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_list_tickets_filter_status(client: TestClient, admin_token: str):
    """按状态筛选工单"""
    client.post(
        "/api/v1/fix-tickets",
        json={"priority": "high"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    res = client.get(
        "/api/v1/fix-tickets?status=OPEN",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["status"] == "OPEN"


def test_get_ticket_detail(client: TestClient, admin_token: str):
    """获取工单详情"""
    r = client.post(
        "/api/v1/fix-tickets",
        json={"priority": "critical", "assignee": "lisi"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    tid = (r.json().get("data") or r.json())["id"]
    res = client.get(
        f"/api/v1/fix-tickets/{tid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["id"] == tid
    assert data["priority"] == "critical"


def test_get_ticket_not_found(client: TestClient, admin_token: str):
    """查询不存在的工单应返回 404"""
    res = client.get(
        "/api/v1/fix-tickets/99999",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 404


# ── 更新工单 ──

def test_update_ticket_status(client: TestClient, admin_token: str):
    """状态流转: OPEN → IN_PROGRESS"""
    r = client.post(
        "/api/v1/fix-tickets",
        json={"priority": "high"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    tid = (r.json().get("data") or r.json())["id"]

    res = client.put(
        f"/api/v1/fix-tickets/{tid}",
        json={"status": "IN_PROGRESS"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["status"] == "IN_PROGRESS"


def test_invalid_status_transition(client: TestClient, admin_token: str):
    """非法状态流转应返回 400"""
    r = client.post(
        "/api/v1/fix-tickets",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    tid = (r.json().get("data") or r.json())["id"]

    res = client.put(
        f"/api/v1/fix-tickets/{tid}",
        json={"status": "CLOSED"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 400


def test_full_lifecycle(client: TestClient, admin_token: str):
    """完整生命周期: OPEN → IN_PROGRESS → RESOLVED → VERIFIED → CLOSED"""
    r = client.post(
        "/api/v1/fix-tickets",
        json={"priority": "high", "assignee": "dev1"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    tid = (r.json().get("data") or r.json())["id"]

    for status in ["IN_PROGRESS", "RESOLVED", "VERIFIED", "CLOSED"]:
        res = client.put(
            f"/api/v1/fix-tickets/{tid}",
            json={"status": status},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        data = res.json().get("data") or res.json()
        assert data["status"] == status

    data = res.json().get("data") or res.json()
    assert data["closed_at"] is not None
