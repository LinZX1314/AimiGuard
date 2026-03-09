"""api/system.py tests — _utc_iso, _ensure_operator_or_admin, _parse_config_json."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from api.system import _utc_iso, _ensure_operator_or_admin, _parse_config_json


# ── _utc_iso ──

def test_utc_iso_format():
    result = _utc_iso()
    assert result.endswith("Z")
    assert "T" in result


# ── _ensure_operator_or_admin ──

def test_ensure_admin_ok():
    user = MagicMock()
    db = MagicMock()
    with patch("api.system.get_user_role", return_value="admin"):
        _ensure_operator_or_admin(user, db)  # should not raise


def test_ensure_operator_ok():
    user = MagicMock()
    db = MagicMock()
    with patch("api.system.get_user_role", return_value="operator"):
        _ensure_operator_or_admin(user, db)


def test_ensure_viewer_rejected():
    user = MagicMock()
    db = MagicMock()
    with patch("api.system.get_user_role", return_value="viewer"):
        with pytest.raises(HTTPException) as exc_info:
            _ensure_operator_or_admin(user, db)
        assert exc_info.value.status_code == 403


# ── _parse_config_json ──

def test_parse_config_json_valid():
    assert _parse_config_json('{"key": "val"}') == {"key": "val"}


def test_parse_config_json_empty():
    assert _parse_config_json("") == {}
    assert _parse_config_json(None) == {}


def test_parse_config_json_invalid():
    assert _parse_config_json("not json") == {}


def test_parse_config_json_non_dict():
    assert _parse_config_json("[1,2,3]") == {}
    assert _parse_config_json('"string"') == {}
