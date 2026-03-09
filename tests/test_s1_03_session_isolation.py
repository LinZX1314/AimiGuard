"""测试 S1-03：对话上下文隔离"""
import pytest
from datetime import datetime, timezone
from starlette.testclient import TestClient
from sqlalchemy.orm import Session as SASession

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


# ── 删除会话 ──

def test_delete_session(client: TestClient, admin_token: str):
    """DELETE /ai/sessions/{id} 应删除会话和消息，列表中不再显示"""
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

    # 删除后访问应返回404
    res2 = client.get(
        f"/api/v1/ai/sessions/{sid}/messages",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res2.status_code == 404


def test_delete_session_service(db: SASession):
    """SessionCleanupService.delete_session 应彻底删除会话和消息"""
    from services.session_cleanup import SessionCleanupService
    now = datetime.now(timezone.utc)

    sess = AIChatSession(user_id=1, operator="admin", created_at=now)
    db.add(sess)
    db.flush()
    db.add(AIChatMessage(session_id=sess.id, role="user", content="test", created_at=now))
    db.commit()
    sid = sess.id

    result = SessionCleanupService.delete_session(db, sid)
    assert result is True
    assert db.query(AIChatSession).filter(AIChatSession.id == sid).first() is None
    assert db.query(AIChatMessage).filter(AIChatMessage.session_id == sid).count() == 0
