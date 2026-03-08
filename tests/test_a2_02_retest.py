"""A2-02 复测触发 测试"""
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session as SASession
from sqlalchemy import text


def _create_ticket(client: TestClient, token: str, **kwargs) -> int:
    """创建工单并返回 id"""
    res = client.post(
        "/api/v1/fix-tickets",
        json=kwargs or {"priority": "high"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    return (res.json().get("data") or res.json())["id"]


def _advance_to_resolved(client: TestClient, token: str, tid: int):
    """推进工单到 RESOLVED 状态"""
    for status in ["IN_PROGRESS", "RESOLVED"]:
        res = client.put(
            f"/api/v1/fix-tickets/{tid}",
            json={"status": status},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200


def test_retest_on_resolved_ticket(client: TestClient, admin_token: str):
    """RESOLVED 状态工单可触发复测"""
    tid = _create_ticket(client, admin_token)
    _advance_to_resolved(client, admin_token, tid)

    res = client.post(
        f"/api/v1/fix-tickets/{tid}/retest",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["ticket_id"] == tid
    assert data["scan_task_id"] is not None
    assert data["state"] == "QUEUED"


def test_retest_on_open_ticket_rejected(client: TestClient, admin_token: str):
    """非 RESOLVED 状态工单不能触发复测"""
    tid = _create_ticket(client, admin_token)
    res = client.post(
        f"/api/v1/fix-tickets/{tid}/retest",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 400
    body = res.json()
    assert "RESOLVED" in body.get("detail", "") or "RESOLVED" in body.get("message", "")


def test_retest_not_found(client: TestClient, admin_token: str):
    """不存在的工单复测应 404"""
    res = client.post(
        "/api/v1/fix-tickets/99999/retest",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 404
