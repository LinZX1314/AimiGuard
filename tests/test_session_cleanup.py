"""SessionCleanupService tests — delete session."""
import pytest
from datetime import datetime, timezone
from core.database import SessionLocal, AIChatSession, AIChatMessage
from services.session_cleanup import SessionCleanupService


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _create_session(db, *, msg_count=3):
    """Helper to create a chat session with messages."""
    now = datetime.now(timezone.utc)

    sess = AIChatSession(
        user_id=1,
        operator="test",
        context_type="test",
        created_at=now,
    )
    db.add(sess)
    db.flush()

    for i in range(msg_count):
        msg = AIChatMessage(
            session_id=sess.id,
            role="user",
            content=f"message {i}",
            created_at=now,
        )
        db.add(msg)
    db.flush()
    return sess


# ── Delete session ──

def test_delete_session(db):
    """Deleting a session removes it and its messages."""
    sess = _create_session(db, msg_count=5)
    db.commit()
    sess_id = sess.id

    result = SessionCleanupService.delete_session(db, sess_id)
    assert result is True

    # Session should be gone
    assert db.query(AIChatSession).filter(AIChatSession.id == sess_id).first() is None

    # Messages should be gone
    msg_count = db.query(AIChatMessage).filter(AIChatMessage.session_id == sess_id).count()
    assert msg_count == 0


def test_delete_nonexistent_session(db):
    """Deleting a nonexistent session returns False."""
    result = SessionCleanupService.delete_session(db, 99999)
    assert result is False


def test_delete_session_no_messages(db):
    """Deleting a session with no messages still succeeds."""
    sess = _create_session(db, msg_count=0)
    db.commit()

    result = SessionCleanupService.delete_session(db, sess.id)
    assert result is True
    assert db.query(AIChatSession).filter(AIChatSession.id == sess.id).first() is None
