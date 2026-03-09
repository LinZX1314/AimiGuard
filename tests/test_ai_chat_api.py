"""api/ai_chat.py tests — _safe_int, verify_session_ownership."""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from fastapi import HTTPException

from api.ai_chat import _safe_int, verify_session_ownership


# ── _safe_int ──

def test_safe_int_valid():
    assert _safe_int("42") == 42


def test_safe_int_none():
    assert _safe_int(None) is None


def test_safe_int_invalid():
    assert _safe_int("abc") is None


def test_safe_int_float_string():
    assert _safe_int("3.14") is None


# ── verify_session_ownership ──

def test_verify_ownership_ok():
    session = MagicMock()
    session.user_id = 1
    session.expires_at = None
    user = MagicMock()
    user.id = 1
    verify_session_ownership(session, user)  # should not raise


def test_verify_ownership_wrong_user():
    session = MagicMock()
    session.user_id = 1
    user = MagicMock()
    user.id = 2
    with pytest.raises(HTTPException) as exc_info:
        verify_session_ownership(session, user)
    assert exc_info.value.status_code == 403


def test_verify_ownership_expired():
    session = MagicMock()
    session.user_id = 1
    session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    user = MagicMock()
    user.id = 1
    with pytest.raises(HTTPException) as exc_info:
        verify_session_ownership(session, user)
    assert exc_info.value.status_code == 410


def test_verify_ownership_not_expired():
    session = MagicMock()
    session.user_id = 1
    session.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    user = MagicMock()
    user.id = 1
    verify_session_ownership(session, user)  # should not raise


def test_verify_ownership_naive_expires_at():
    session = MagicMock()
    session.user_id = 1
    # naive datetime (no tzinfo) — treated as UTC by the code
    session.expires_at = datetime(2020, 1, 1)
    user = MagicMock()
    user.id = 1
    with pytest.raises(HTTPException) as exc_info:
        verify_session_ownership(session, user)
    assert exc_info.value.status_code == 410
