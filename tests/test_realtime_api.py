"""api/realtime.py tests — _get_token_from_query, _authorize_websocket."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from api.realtime import _get_token_from_query, _authorize_websocket


# ── _get_token_from_query ──

def test_get_token_strips():
    assert _get_token_from_query("  abc  ") == "abc"


def test_get_token_empty():
    assert _get_token_from_query("") == ""


def test_get_token_default():
    assert _get_token_from_query("") == ""


# ── _authorize_websocket ──

def test_authorize_has_permission():
    user = MagicMock()
    db = MagicMock()
    with patch("api.realtime.resolve_current_user_from_token", return_value=user):
        with patch("api.realtime.get_user_permissions", return_value=["view_events", "scan:view"]):
            result = _authorize_websocket("tok", "view_events", db)
    assert result == user


def test_authorize_missing_permission():
    user = MagicMock()
    db = MagicMock()
    with patch("api.realtime.resolve_current_user_from_token", return_value=user):
        with patch("api.realtime.get_user_permissions", return_value=["scan:view"]):
            with pytest.raises(HTTPException) as exc_info:
                _authorize_websocket("tok", "view_events", db)
            assert exc_info.value.status_code == 403
