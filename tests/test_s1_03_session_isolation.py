"""测试 S1-03：对话上下文隔离"""
import pytest
from datetime import datetime, timedelta, timezone
from starlette.testclient import TestClient
from sqlalchemy.orm import Session as SASession
from sqlalchemy import text

from core.database import AIChatSession, AIChatMessage


# ── 会话归属隔离 ──

def test_context_endpoint_own_session(client: TestClient, admin_token: str):
    """用户可以访问自己创建的会话上下文"""
    res = client.post(
        "/api/v1/ai/chat",
        json={"message": "测试会话上下文"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    session_id = (res.json().get("data") or res.json())["session_id"]

    res2 = client.get(
        f"/api/v1/ai/chat/{session_id}/context",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res2.status_code == 200
    data = res2.json().get("data") or res2.json()
    assert data["session_id"] == session_id
    assert len(data["messages"]) >= 1


def test_context_nonexistent_session(client: TestClient, admin_token: str):
    """不存在的会话应返回404"""
    res = client.get(
        "/api/v1/ai/chat/99999/context",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 404


def test_session_messages_isolation(client: TestClient, admin_token: str):
    """不同会话的消息应完全隔离"""
    r1 = client.post(
        "/api/v1/ai/chat",
        json={"message": "会话A的消息"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    sid1 = (r1.json().get("data") or r1.json())["session_id"]

    r2 = client.post(
        "/api/v1/ai/chat",
        json={"message": "会话B的消息"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    sid2 = (r2.json().get("data") or r2.json())["session_id"]

    ctx1 = client.get(
        f"/api/v1/ai/chat/{sid1}/context",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["data"]
    ctx2 = client.get(
        f"/api/v1/ai/chat/{sid2}/context",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["data"]

    assert ctx1["messages"][0]["content"] != ctx2["messages"][0]["content"]


# ── 会话过期 ──

def test_expired_session_rejected(client: TestClient, admin_token: str, db: SASession):
    """访问过期会话应返回410"""
    db.execute(
        text(
            "INSERT INTO ai_chat_session (user_id, operator, started_at, expires_at) "
            "VALUES (1, 'admin', datetime('now', '-25 hours'), datetime('now', '-1 hour'))"
        )
    )
    db.commit()
    row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
    sid = row[0]

    res = client.get(
        f"/api/v1/ai/sessions/{sid}/messages",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 410


# ── 过期会话清理API ──

def test_cleanup_expired_sessions_api(client: TestClient, admin_token: str, db: SASession):
    """POST /ai/sessions/cleanup-expired 应清理过期会话"""
    db.execute(
        text(
            "INSERT INTO ai_chat_session (user_id, operator, started_at, expires_at) "
            "VALUES (1, 'admin', datetime('now', '-48 hours'), datetime('now', '-24 hours'))"
        )
    )
    db.commit()
    row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
    sid = row[0]

    db.execute(
        text(
            "INSERT INTO ai_chat_message (session_id, role, content, created_at) "
            "VALUES (:sid, 'user', '过期消息', datetime('now', '-48 hours'))"
        ),
        {"sid": sid},
    )
    db.commit()

    res = client.post(
        "/api/v1/ai/sessions/cleanup-expired",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["cleaned_sessions"] >= 1


# ── SessionCleanupService ──

def test_session_cleanup_service(db: SASession):
    """SessionCleanupService应清理过期会话"""
    from services.session_cleanup import SessionCleanupService

    db.execute(
        text(
            "INSERT INTO ai_chat_session (user_id, operator, started_at, expires_at) "
            "VALUES (1, 'admin', datetime('now', '-48 hours'), datetime('now', '-2 hours'))"
        )
    )
    db.commit()
    row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
    sid = row[0]

    db.execute(
        text(
            "INSERT INTO ai_chat_message (session_id, role, content, created_at) "
            "VALUES (:sid, 'user', 'expired msg', datetime('now'))"
        ),
        {"sid": sid},
    )
    db.commit()

    cleaned = SessionCleanupService.cleanup_expired_sessions(db)
    assert cleaned >= 1

    msgs = db.execute(
        text("SELECT count(*) FROM ai_chat_message WHERE session_id = :sid"),
        {"sid": sid},
    ).fetchone()
    assert msgs[0] == 0


def test_force_end_session(client: TestClient, admin_token: str, db: SASession):
    """force_end_session应结束会话并清除消息"""
    from services.session_cleanup import SessionCleanupService

    r = client.post(
        "/api/v1/ai/chat",
        json={"message": "将被强制结束"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    sid = (r.json().get("data") or r.json())["session_id"]

    result = SessionCleanupService.force_end_session(db, sid)
    assert result is True

    session = db.query(AIChatSession).filter(AIChatSession.id == sid).first()
    assert session.ended_at is not None


# ── 删除会话 ──

def test_delete_session(client: TestClient, admin_token: str):
    """DELETE /ai/sessions/{id} 应删除会话和消息"""
    r = client.post(
        "/api/v1/ai/chat",
        json={"message": "将被删除"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    sid = (r.json().get("data") or r.json())["session_id"]

    res = client.delete(
        f"/api/v1/ai/sessions/{sid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
