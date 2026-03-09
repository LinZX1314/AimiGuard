"""api/overview.py tests — helper functions: _iso_z, _config_bool, _status_item."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from api.overview import _iso_z, _config_bool, _status_item, _config_map


# ── _iso_z ──

def test_iso_z_utc():
    dt = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    result = _iso_z(dt)
    assert result.endswith("Z")
    assert "2025-06-15" in result


def test_iso_z_none():
    assert _iso_z(None) is None


# ── _config_bool ──

def test_config_bool_true():
    configs = {"enabled": "true"}
    assert _config_bool(configs) is True


def test_config_bool_false():
    configs = {"enabled": "false"}
    assert _config_bool(configs) is False


def test_config_bool_missing_default_false():
    assert _config_bool({}) is False


def test_config_bool_missing_default_true():
    assert _config_bool({}, default=True) is True


def test_config_bool_various_true_values():
    for v in ("1", "yes", "on", "True"):
        assert _config_bool({"enabled": v}) is True


# ── _status_item ──

def test_status_item():
    item = _status_item("hfish", "HFish", True, "running", "10/min")
    assert item["key"] == "hfish"
    assert item["ok"] is True
    assert item["metric"] == "10/min"


def test_status_item_no_metric():
    item = _status_item("nmap", "Nmap", False, "disabled")
    assert item["metric"] is None


# ── _config_map ──

def test_config_map():
    mock_db = MagicMock()
    row1 = MagicMock()
    row1.config_key = "enabled"
    row1.config_value = "true"
    row2 = MagicMock()
    row2.config_key = "host"
    row2.config_value = "localhost"
    mock_db.query.return_value.filter.return_value.all.return_value = [row1, row2]
    result = _config_map(mock_db, "hfish")
    assert result["enabled"] == "true"
    assert result["host"] == "localhost"


def test_config_map_empty():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = []
    result = _config_map(mock_db, "hfish")
    assert result == {}
