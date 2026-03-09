"""ModeService tests — get/set mode, audit logging, persistence."""
import json
import pytest
from datetime import datetime, timezone
from core.database import SessionLocal, SystemConfigSnapshot
from services.mode_service import get_current_mode, set_mode, MODE_CONFIG_KEY


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


ENV = "test"


# ── get_current_mode ──

def test_get_default_mode(db):
    """No snapshot → returns PASSIVE default."""
    result = get_current_mode(db, env="nonexistent_env_xyz")
    assert result["mode"] == "PASSIVE"
    assert result["operator"] == "system"
    assert "updated_at" in result


def test_get_mode_after_set(db):
    """After set_mode, get_current_mode returns the new mode."""
    set_mode(db, mode="ACTIVE", reason="测试切换", operator="admin", env=ENV, trace_id="t1")
    result = get_current_mode(db, ENV)
    assert result["mode"] == "ACTIVE"
    assert result["reason"] == "测试切换"
    assert result["operator"] == "admin"


# ── set_mode ──

def test_set_mode_returns_payload(db):
    payload = set_mode(db, mode="ACTIVE", reason="启动主动", operator="admin", env=ENV, trace_id="t2")
    assert payload["mode"] == "ACTIVE"
    assert payload["reason"] == "启动主动"
    assert payload["operator"] == "admin"
    assert "updated_at" in payload


def test_set_mode_creates_snapshot(db):
    set_mode(db, mode="ACTIVE", reason="test", operator="tester", env=ENV, trace_id="t3")
    snap = db.query(SystemConfigSnapshot).filter(
        SystemConfigSnapshot.config_key == MODE_CONFIG_KEY,
        SystemConfigSnapshot.env == ENV,
    ).order_by(SystemConfigSnapshot.id.desc()).first()
    assert snap is not None
    data = json.loads(snap.config_value)
    assert data["mode"] == "ACTIVE"


def test_set_mode_passive(db):
    set_mode(db, mode="ACTIVE", reason="先切主动", operator="admin", env=ENV, trace_id="t4")
    set_mode(db, mode="PASSIVE", reason="切回被动", operator="admin", env=ENV, trace_id="t5")
    result = get_current_mode(db, ENV)
    assert result["mode"] == "PASSIVE"
    assert result["reason"] == "切回被动"


def test_set_mode_writes_audit(db):
    """set_mode should create an audit log entry."""
    from core.database import AuditLog
    before = db.query(AuditLog).filter(AuditLog.action.like("set_mode%")).count()
    set_mode(db, mode="ACTIVE", reason="audit test", operator="admin", env=ENV, trace_id="t6")
    after = db.query(AuditLog).filter(AuditLog.action.like("set_mode%")).count()
    assert after > before


def test_set_mode_invalid_then_get_defaults_passive(db):
    """If stored mode is garbage, get_current_mode falls back to PASSIVE."""
    now = datetime.now(timezone.utc)
    snap = SystemConfigSnapshot(
        config_key=MODE_CONFIG_KEY,
        config_value=json.dumps({"mode": "INVALID", "reason": "bad"}),
        source="test",
        env="fallback_env",
        loaded_at=now,
        created_at=now,
    )
    db.add(snap)
    db.commit()
    result = get_current_mode(db, "fallback_env")
    assert result["mode"] == "PASSIVE"


def test_set_mode_malformed_json(db):
    """Malformed JSON in config_value → defaults to PASSIVE."""
    now = datetime.now(timezone.utc)
    snap = SystemConfigSnapshot(
        config_key=MODE_CONFIG_KEY,
        config_value="not-json{{{",
        source="test",
        env="malformed_env",
        loaded_at=now,
        created_at=now,
    )
    db.add(snap)
    db.commit()
    result = get_current_mode(db, "malformed_env")
    assert result["mode"] == "PASSIVE"


def test_set_mode_with_none_reason(db):
    payload = set_mode(db, mode="ACTIVE", reason=None, operator="admin", env=ENV, trace_id="t7")
    assert payload["reason"] is None
    result = get_current_mode(db, ENV)
    assert result["mode"] == "ACTIVE"
