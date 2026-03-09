"""api/honeytoken.py tests — token generation, token_to_dict, valid types."""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from api.honeytoken import _generate_token_value, _token_to_dict, VALID_TOKEN_TYPES


# ── _generate_token_value ──

def test_generate_credential():
    val = _generate_token_value("credential")
    assert ":" in val


def test_generate_api_key():
    val = _generate_token_value("api_key")
    assert val.startswith("sk-honey-")


def test_generate_document():
    val = _generate_token_value("document")
    assert val.startswith("doc-tracker-")
    assert val.endswith(".pdf")


def test_generate_url():
    val = _generate_token_value("url")
    assert val.startswith("https://trap.internal/")


def test_generate_unknown_type():
    val = _generate_token_value("unknown")
    assert len(val) == 32  # token_hex(16)


def test_generate_unique():
    a = _generate_token_value("api_key")
    b = _generate_token_value("api_key")
    assert a != b


# ── VALID_TOKEN_TYPES ──

def test_valid_types():
    assert "credential" in VALID_TOKEN_TYPES
    assert "api_key" in VALID_TOKEN_TYPES
    assert "document" in VALID_TOKEN_TYPES
    assert "url" in VALID_TOKEN_TYPES


# ── _token_to_dict ──

def test_token_to_dict():
    t = MagicMock()
    t.id = 1
    t.token_type = "api_key"
    t.value_hash = "abc123"
    t.deployed_location = "/var/secrets"
    t.status = "ACTIVE"
    t.triggered_at = None
    t.attacker_ip = None
    t.trigger_count = 0
    t.trace_id = "tr1"
    t.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

    d = _token_to_dict(t)
    assert d["id"] == 1
    assert d["token_type"] == "api_key"
    assert d["triggered_at"] is None
    assert d["created_at"] == "2025-01-01T00:00:00+00:00"


def test_token_to_dict_triggered():
    t = MagicMock()
    t.id = 2
    t.token_type = "credential"
    t.value_hash = "xyz"
    t.deployed_location = None
    t.status = "TRIGGERED"
    t.triggered_at = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
    t.attacker_ip = "10.0.0.99"
    t.trigger_count = 3
    t.trace_id = "tr2"
    t.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

    d = _token_to_dict(t)
    assert d["status"] == "TRIGGERED"
    assert d["attacker_ip"] == "10.0.0.99"
    assert d["trigger_count"] == 3
    assert "2025-06-15" in d["triggered_at"]
