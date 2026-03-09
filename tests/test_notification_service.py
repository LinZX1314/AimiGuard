"""NotificationService unit tests — create, broadcast, list, mark read."""
import pytest
from core.database import SessionLocal, Notification, User
from services.notification_service import NotificationService


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _ensure_user(db, user_id=1):
    """Make sure test user exists."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        user = User(
            id=user_id,
            username=f"testuser_{user_id}",
            password_hash="fakehash",
            enabled=1,
        )
        db.add(user)
        db.flush()
    return user


# ── Create ──

def test_create_notification_for_user(db):
    _ensure_user(db)
    nid = NotificationService.create(
        db, title="测试通知", content="内容", user_id=1, category="alert", severity="warning",
    )
    assert nid is not None
    n = db.query(Notification).filter(Notification.id == nid).first()
    assert n.title == "测试通知"
    assert n.category == "alert"
    assert n.severity == "warning"
    assert n.read == 0


def test_create_notification_defaults(db):
    _ensure_user(db)
    nid = NotificationService.create(db, title="默认", user_id=1)
    n = db.query(Notification).filter(Notification.id == nid).first()
    assert n.category == "system"
    assert n.severity == "info"


def test_create_broadcast_to_all_users(db):
    u1 = _ensure_user(db, 1)
    u2 = _ensure_user(db, 2)
    db.flush()

    nid = NotificationService.create(
        db, title="广播通知", content="全体", user_id=None,
    )
    assert nid is not None
    # Both users should have a notification
    n1 = db.query(Notification).filter(
        Notification.user_id == u1.id, Notification.title == "广播通知",
    ).first()
    n2 = db.query(Notification).filter(
        Notification.user_id == u2.id, Notification.title == "广播通知",
    ).first()
    assert n1 is not None
    assert n2 is not None


# ── List ──

def test_list_for_user(db):
    _ensure_user(db)
    NotificationService.create(db, title="n1", user_id=1)
    NotificationService.create(db, title="n2", user_id=1)
    result = NotificationService.list_for_user(db, user_id=1)
    assert result["total"] >= 2
    assert result["unread"] >= 2
    assert len(result["items"]) >= 2
    titles = [i["title"] for i in result["items"]]
    assert "n1" in titles
    assert "n2" in titles


def test_list_unread_only(db):
    _ensure_user(db)
    nid = NotificationService.create(db, title="已读", user_id=1)
    NotificationService.mark_read(db, nid, 1)
    NotificationService.create(db, title="未读", user_id=1)
    result = NotificationService.list_for_user(db, user_id=1, unread_only=True)
    titles = [i["title"] for i in result["items"]]
    assert "未读" in titles
    assert "已读" not in titles


def test_list_pagination(db):
    _ensure_user(db)
    for i in range(5):
        NotificationService.create(db, title=f"page_{i}", user_id=1)
    result = NotificationService.list_for_user(db, user_id=1, limit=2, offset=0)
    assert len(result["items"]) == 2


# ── Mark read ──

def test_mark_read(db):
    _ensure_user(db)
    nid = NotificationService.create(db, title="待读", user_id=1)
    ok = NotificationService.mark_read(db, nid, 1)
    assert ok is True
    n = db.query(Notification).filter(Notification.id == nid).first()
    assert n.read == 1


def test_mark_read_wrong_user(db):
    _ensure_user(db, 1)
    _ensure_user(db, 2)
    nid = NotificationService.create(db, title="user1的", user_id=1)
    ok = NotificationService.mark_read(db, nid, 2)
    assert ok is False


def test_mark_read_nonexistent(db):
    ok = NotificationService.mark_read(db, 99999, 1)
    assert ok is False


def test_mark_all_read(db):
    _ensure_user(db)
    NotificationService.create(db, title="a", user_id=1)
    NotificationService.create(db, title="b", user_id=1)
    count = NotificationService.mark_all_read(db, 1)
    assert count >= 2
    result = NotificationService.list_for_user(db, user_id=1, unread_only=True)
    assert result["unread"] == 0


# ── Broadcast helper ──

def test_broadcast_uses_factory(db):
    _ensure_user(db)
    db.commit()
    NotificationService.broadcast(
        SessionLocal, title="factory广播", content="test", trace_id="tr1",
    )
    fresh = SessionLocal()
    try:
        n = fresh.query(Notification).filter(
            Notification.title == "factory广播",
        ).first()
        assert n is not None
    finally:
        fresh.close()
