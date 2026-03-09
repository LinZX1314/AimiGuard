"""api/auth.py tests — password hashing, token resolution, blacklist, helpers."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone
from jose import jwt
from fastapi import HTTPException

from api.auth import (
    hash_password,
    verify_password,
    get_user_role,
    resolve_current_user_from_token,
    BLACKLISTED_TOKENS,
    SECRET_KEY,
    ALGORITHM,
)


# ── hash_password / verify_password ──

def test_hash_password_deterministic():
    assert hash_password("abc") == hash_password("abc")


def test_hash_password_different():
    assert hash_password("a") != hash_password("b")


def test_verify_password_correct():
    h = hash_password("secret")
    assert verify_password("secret", h) is True


def test_verify_password_wrong():
    h = hash_password("secret")
    assert verify_password("wrong", h) is False


# ── get_user_role ──

def test_get_user_role_found():
    user = MagicMock()
    user.id = 1
    db = MagicMock()
    user_role_mock = MagicMock()
    user_role_mock.role_id = 10
    role_mock = MagicMock()
    role_mock.name = "admin"
    db.query.return_value.filter.return_value.first.side_effect = [user_role_mock, role_mock]
    assert get_user_role(user, db) == "admin"


def test_get_user_role_no_role():
    user = MagicMock()
    user.id = 1
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    assert get_user_role(user, db) == "viewer"


# ── resolve_current_user_from_token ──

def test_resolve_valid_token():
    token_data = {
        "sub": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    db = MagicMock()
    user_mock = MagicMock()
    user_mock.enabled = 1
    db.query.return_value.filter.return_value.first.return_value = user_mock
    result = resolve_current_user_from_token(token, db)
    assert result == user_mock


def test_resolve_expired_token():
    token_data = {
        "sub": "admin",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    db = MagicMock()
    with pytest.raises(HTTPException) as exc_info:
        resolve_current_user_from_token(token, db)
    assert exc_info.value.status_code == 401


def test_resolve_invalid_token():
    db = MagicMock()
    with pytest.raises(HTTPException) as exc_info:
        resolve_current_user_from_token("not.a.valid.token", db)
    assert exc_info.value.status_code == 401


def test_resolve_blacklisted_token():
    token_data = {
        "sub": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    BLACKLISTED_TOKENS.add(token)
    db = MagicMock()
    try:
        with pytest.raises(HTTPException) as exc_info:
            resolve_current_user_from_token(token, db)
        assert exc_info.value.status_code == 401
    finally:
        BLACKLISTED_TOKENS.discard(token)


def test_resolve_token_no_sub():
    token_data = {
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    db = MagicMock()
    with pytest.raises(HTTPException) as exc_info:
        resolve_current_user_from_token(token, db)
    assert exc_info.value.status_code == 401


def test_resolve_token_user_disabled():
    token_data = {
        "sub": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    db = MagicMock()
    user_mock = MagicMock()
    user_mock.enabled = 0
    db.query.return_value.filter.return_value.first.return_value = user_mock
    with pytest.raises(HTTPException) as exc_info:
        resolve_current_user_from_token(token, db)
    assert exc_info.value.status_code == 401


def test_resolve_token_user_not_found():
    token_data = {
        "sub": "ghost",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        resolve_current_user_from_token(token, db)
    assert exc_info.value.status_code == 401
