"""api/firewall.py tests — helper functions: hash, bool, int, iso_z."""
from datetime import datetime, timezone

from api.firewall import _compute_request_hash, _to_bool, _to_int, _iso_z


# ── _compute_request_hash ──

def test_hash_deterministic():
    h1 = _compute_request_hash("10.0.0.1", "block", "paloalto")
    h2 = _compute_request_hash("10.0.0.1", "block", "paloalto")
    assert h1 == h2
    assert len(h1) == 64


def test_hash_different_inputs():
    assert _compute_request_hash("10.0.0.1", "block", "pa") != _compute_request_hash("10.0.0.2", "block", "pa")


# ── _to_bool ──

def test_to_bool_true_values():
    for v in ("1", "true", "yes", "on", "  True  ", " YES "):
        assert _to_bool(v) is True


def test_to_bool_false_values():
    for v in ("0", "false", "no", "off", "random"):
        assert _to_bool(v) is False


def test_to_bool_none_default():
    assert _to_bool(None) is False
    assert _to_bool(None, default=True) is True


# ── _to_int ──

def test_to_int_valid():
    assert _to_int("42", 0) == 42


def test_to_int_invalid():
    assert _to_int("abc", 99) == 99


def test_to_int_none():
    assert _to_int(None, 10) == 10


# ── _iso_z ──

def test_iso_z_with_datetime():
    dt = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    result = _iso_z(dt)
    assert result.endswith("Z")
    assert "2025-06-15" in result


def test_iso_z_none():
    assert _iso_z(None) is None
