"""api/defense.py tests — pure helper functions."""
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from api.defense import (
    _safe_int,
    _to_flag,
    _json_dumps,
    _normalize_label,
    _parse_hfish_time,
    _iso_z,
    _get_defense_runtime_workflow_key,
)


# ── _safe_int ──

def test_safe_int_valid():
    assert _safe_int("42") == 42
    assert _safe_int(3.9) == 3


def test_safe_int_invalid():
    assert _safe_int("abc", 99) == 99
    assert _safe_int(None, 5) == 5


# ── _to_flag ──

def test_to_flag_bool():
    assert _to_flag(True) == 1
    assert _to_flag(False) == 0


def test_to_flag_int():
    assert _to_flag(1) == 1
    assert _to_flag(0) == 0


def test_to_flag_string():
    for v in ("1", "true", "yes", "y", "on"):
        assert _to_flag(v) == 1
    for v in ("0", "false", "no", "off"):
        assert _to_flag(v) == 0


def test_to_flag_other():
    assert _to_flag(None) == 0
    assert _to_flag([]) == 0


# ── _json_dumps ──

def test_json_dumps_dict():
    result = _json_dumps({"key": "值"})
    assert "值" in result


def test_json_dumps_datetime():
    dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
    result = _json_dumps({"ts": dt})
    assert "2025" in result


# ── _normalize_label ──

def test_normalize_label_string():
    assert _normalize_label("brute_force", None) == "brute_force"


def test_normalize_label_list():
    assert _normalize_label(["ssh", "rdp"], None) == "ssh,rdp"


def test_normalize_label_cn_fallback():
    assert _normalize_label(None, "暴力破解") == "暴力破解"


def test_normalize_label_empty():
    assert _normalize_label(None, None) == "unknown"
    assert _normalize_label("", "") == "unknown"


def test_normalize_label_list_with_blanks():
    assert _normalize_label(["", "ssh", ""], None) == "ssh"


# ── _parse_hfish_time ──

def test_parse_hfish_time_none():
    assert _parse_hfish_time(None) is None


def test_parse_hfish_time_datetime():
    dt = datetime(2025, 6, 1, tzinfo=timezone.utc)
    assert _parse_hfish_time(dt) == dt


def test_parse_hfish_time_timestamp():
    result = _parse_hfish_time(1700000000)
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


def test_parse_hfish_time_iso_string():
    result = _parse_hfish_time("2025-06-01T12:00:00Z")
    assert isinstance(result, datetime)


def test_parse_hfish_time_standard_format():
    result = _parse_hfish_time("2025-06-01 12:00:00")
    assert isinstance(result, datetime)


def test_parse_hfish_time_invalid():
    assert _parse_hfish_time("not a date") is None


def test_parse_hfish_time_empty_string():
    assert _parse_hfish_time("") is None


# ── _iso_z ──

def test_iso_z_utc():
    dt = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
    result = _iso_z(dt)
    assert result.endswith("Z")


def test_iso_z_none():
    assert _iso_z(None) is None


# ── _get_defense_runtime_workflow_key ──

def test_workflow_key_default():
    with patch.dict("os.environ", {}, clear=True):
        assert _get_defense_runtime_workflow_key() == "defense_default"


def test_workflow_key_custom():
    with patch.dict("os.environ", {"DEFENSE_RUNTIME_WORKFLOW_KEY": "custom_wf"}):
        assert _get_defense_runtime_workflow_key() == "custom_wf"


def test_workflow_key_empty():
    with patch.dict("os.environ", {"DEFENSE_RUNTIME_WORKFLOW_KEY": "  "}):
        assert _get_defense_runtime_workflow_key() == "defense_default"
