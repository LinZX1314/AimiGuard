"""Notification API + service tests."""
import pytest
from core.database import Notification
from services.notification_service import NotificationService


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Service layer ──

def test_create_notification_for_user(db):
    nid = NotificationService.create(
        db, title="测试通知", content="内容", category="alert",
        severity="warning", user_id=1, trace_id="t-n1",
    )
    assert nid is not None
    n = db.query(Notification).filter(Notification.id == nid).first()
    assert n.title == "测试通知"
    assert n.read == 0


def test_create_notification_broadcast(db):
    nid = NotificationService.create(
        db, title="广播通知", content="全员", user_id=None,
    )
    assert nid is not None
    count = db.query(Notification).filter(Notification.title == "广播通知").count()
    assert count >= 1  # at least one user


def test_mark_read(db):
    nid = NotificationService.create(db, title="标记已读", user_id=1)
    assert NotificationService.mark_read(db, nid, user_id=1) is True
    n = db.query(Notification).filter(Notification.id == nid).first()
    assert n.read == 1


def test_mark_read_wrong_user(db):
    nid = NotificationService.create(db, title="别人的通知", user_id=1)
    assert NotificationService.mark_read(db, nid, user_id=9999) is False


def test_mark_read_not_found(db):
    assert NotificationService.mark_read(db, 99999, user_id=1) is False


def test_mark_all_read(db):
    for i in range(3):
        NotificationService.create(db, title=f"批量已读{i}", user_id=1)
    count = NotificationService.mark_all_read(db, user_id=1)
    assert count >= 3


def test_list_for_user(db):
    for i in range(5):
        NotificationService.create(db, title=f"列表测试{i}", user_id=1, severity="info")
    data = NotificationService.list_for_user(db, user_id=1, limit=3)
    assert data["total"] >= 5
    assert len(data["items"]) == 3
    assert "unread" in data


def test_list_unread_only(db):
    nid = NotificationService.create(db, title="已读项", user_id=1)
    NotificationService.mark_read(db, nid, user_id=1)
    NotificationService.create(db, title="未读项", user_id=1)
    data = NotificationService.list_for_user(db, user_id=1, unread_only=True)
    for item in data["items"]:
        assert item["read"] is False


# ── API layer ──

def test_api_list_notifications(client, admin_token, db):
    NotificationService.create(db, title="API列表", user_id=1)
    resp = client.get("/api/v1/notifications", headers=_h(admin_token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total" in data
    assert "items" in data


def test_api_mark_read(client, admin_token, db):
    nid = NotificationService.create(db, title="API已读", user_id=1)
    resp = client.post(f"/api/v1/notifications/{nid}/read", headers=_h(admin_token))
    assert resp.status_code == 200


def test_api_mark_read_not_found(client, admin_token):
    resp = client.post("/api/v1/notifications/99999/read", headers=_h(admin_token))
    assert resp.status_code == 404


def test_api_mark_all_read(client, admin_token, db):
    for i in range(3):
        NotificationService.create(db, title=f"全部已读{i}", user_id=1)
    resp = client.post("/api/v1/notifications/read-all", headers=_h(admin_token))
    assert resp.status_code == 200
    assert resp.json()["data"]["marked"] >= 3
