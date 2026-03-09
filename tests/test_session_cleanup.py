"""SessionCleanupService tests — expired session cleanup and force end."""
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
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


def _create_session(db, *, expired=False, ended=False, msg_count=3):
    """Helper to create a chat session with messages."""
    now = datetime.now(timezone.utc)
    expires = now - timedelta(hours=1) if expired else now + timedelta(hours=1)
    ended_at = now if ended else None

    sess = AIChatSession(
        user_id=1,
        operator="test",
        context_type="test",
        expires_at=expires,
        ended_at=ended_at,
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


# ── Cleanup expired sessions ──

def test_cleanup_no_expired(db):
    """No expired sessions → cleaned count is 0."""
    _create_session(db, expired=False)
    db.commit()
    count = SessionCleanupService.cleanup_expired_sessions(db)
    assert count == 0


def test_cleanup_expired_session(db):
    """Expired + not ended session should be cleaned."""
    sess = _create_session(db, expired=True, ended=False, msg_count=5)
    db.commit()
    sess_id = sess.id

    count = SessionCleanupService.cleanup_expired_sessions(db)
    assert count == 1

    # Session should be marked as ended
    refreshed = db.query(AIChatSession).filter(AIChatSession.id == sess_id).first()
    assert refreshed.ended_at is not None

    # Messages should be deleted
    msg_count = db.query(AIChatMessage).filter(AIChatMessage.session_id == sess_id).count()
    assert msg_count == 0


def test_cleanup_already_ended_skipped(db):
    """Expired but already ended sessions should not be re-cleaned."""
    _create_session(db, expired=True, ended=True, msg_count=3)
    db.commit()

    count = SessionCleanupService.cleanup_expired_sessions(db)
    assert count == 0


def test_cleanup_multiple_expired(db):
    """Multiple expired sessions cleaned in one call."""
    _create_session(db, expired=True, ended=False, msg_count=2)
    _create_session(db, expired=True, ended=False, msg_count=4)
    _create_session(db, expired=False, ended=False, msg_count=1)
    db.commit()

    count = SessionCleanupService.cleanup_expired_sessions(db)
    assert count == 2


# ── Force end session ──

def test_force_end_session(db):
    """Force ending an active session."""
    sess = _create_session(db, expired=False, ended=False, msg_count=3)
    db.commit()
    sess_id = sess.id

    result = SessionCleanupService.force_end_session(db, sess_id)
    assert result is True

    refreshed = db.query(AIChatSession).filter(AIChatSession.id == sess_id).first()
    assert refreshed.ended_at is not None

    msg_count = db.query(AIChatMessage).filter(AIChatMessage.session_id == sess_id).count()
    assert msg_count == 0


def test_force_end_nonexistent_session(db):
    """Force ending a nonexistent session returns False."""
    result = SessionCleanupService.force_end_session(db, 99999)
    assert result is False


def test_force_end_already_ended(db):
    """Force ending an already-ended session still succeeds."""
    sess = _create_session(db, expired=False, ended=True, msg_count=2)
    db.commit()

    result = SessionCleanupService.force_end_session(db, sess.id)
    assert result is True
