"""HFishCollector tests — config, timestamp, event ID, threat mapping, ingest."""
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from services.hfish_collector import HFishCollector


# ── Init ──

def test_init_defaults():
    hc = HFishCollector()
    assert hc.host_port is None
    assert hc.api_key is None
    assert hc.sync_interval == 60
    assert hc.enabled is False


# ── _timestamp_to_datetime ──

def test_timestamp_seconds():
    dt = HFishCollector._timestamp_to_datetime(1700000000)
    assert isinstance(dt, datetime)
    assert dt.tzinfo is not None


def test_timestamp_milliseconds():
    dt = HFishCollector._timestamp_to_datetime(1700000000000)
    assert isinstance(dt, datetime)


def test_timestamp_zero():
    assert HFishCollector._timestamp_to_datetime(0) is None


def test_timestamp_none():
    assert HFishCollector._timestamp_to_datetime(None) is None


def test_timestamp_invalid():
    assert HFishCollector._timestamp_to_datetime("not_a_number") is None


# ── _build_event_id ──

def test_build_event_id_deterministic():
    hc = HFishCollector()
    log = {"attack_ip": "10.0.0.1", "service_name": "ssh", "service_port": "22", "create_time": 1700000000}
    id1 = hc._build_event_id(log)
    id2 = hc._build_event_id(log)
    assert id1 == id2
    assert len(id1) == 32  # md5 hex


def test_build_event_id_different():
    hc = HFishCollector()
    log1 = {"attack_ip": "10.0.0.1", "service_name": "ssh"}
    log2 = {"attack_ip": "10.0.0.2", "service_name": "ssh"}
    assert hc._build_event_id(log1) != hc._build_event_id(log2)


# ── _map_threat_level_to_score ──

def test_threat_level_high():
    hc = HFishCollector()
    assert hc._map_threat_level_to_score("高危") == 80
    assert hc._map_threat_level_to_score("high") == 80


def test_threat_level_medium():
    hc = HFishCollector()
    assert hc._map_threat_level_to_score("中危") == 50
    assert hc._map_threat_level_to_score("medium") == 50


def test_threat_level_low():
    hc = HFishCollector()
    assert hc._map_threat_level_to_score("低危") == 20
    assert hc._map_threat_level_to_score("low") == 20


def test_threat_level_unknown():
    hc = HFishCollector()
    assert hc._map_threat_level_to_score("unknown") == 50


# ── fetch_attack_logs ──

def test_fetch_no_config():
    hc = HFishCollector()
    hc.api_key = None
    hc.host_port = None
    assert hc.fetch_attack_logs() == []


def test_fetch_api_error():
    hc = HFishCollector()
    hc.api_key = "key"
    hc.host_port = "localhost:4433"
    with patch("services.hfish_collector.requests.post", side_effect=ConnectionError("refused")):
        result = hc.fetch_attack_logs()
    assert result == []


def test_fetch_api_non_200_code():
    hc = HFishCollector()
    hc.api_key = "key"
    hc.host_port = "localhost:4433"
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"code": 500, "msg": "server error"}
    with patch("services.hfish_collector.requests.post", return_value=mock_resp):
        result = hc.fetch_attack_logs()
    assert result == []


def test_fetch_api_success():
    hc = HFishCollector()
    hc.api_key = "key"
    hc.api_base_url = "https://hfish.local"
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "code": 200,
        "data": {"detail_list": [{"attack_ip": "10.0.0.1"}]},
    }
    with patch("services.hfish_collector.requests.post", return_value=mock_resp):
        result = hc.fetch_attack_logs()
    assert len(result) == 1


# ── ingest_logs ──

def test_ingest_empty():
    hc = HFishCollector()
    mock_db = MagicMock()
    assert hc.ingest_logs([], mock_db, "tr1") == 0


def test_ingest_skip_duplicate():
    hc = HFishCollector()
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()  # existing
    logs = [{"attack_ip": "10.0.0.1", "service_name": "ssh", "service_port": "22", "create_time": 0}]
    count = hc.ingest_logs(logs, mock_db, "tr1")
    assert count == 0


# ── sync_once ──

@pytest.mark.asyncio
async def test_sync_once_disabled():
    hc = HFishCollector()
    hc.enabled = False
    hc._config_loaded = True
    result = await hc.sync_once("tr1")
    assert result["success"] is False
    assert "未启用" in result["message"]


@pytest.mark.asyncio
async def test_sync_once_no_data():
    hc = HFishCollector()
    hc.enabled = True
    hc._config_loaded = True
    hc.api_key = "key"
    hc.host_port = "localhost"
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    with patch("services.hfish_collector.SessionLocal", return_value=mock_db):
        with patch.object(hc, "fetch_attack_logs", return_value=[]):
            result = await hc.sync_once("tr2")
    assert result["success"] is True
    assert result["count"] == 0


# ── _load_config ──

def test_load_config_db_failure():
    hc = HFishCollector()
    mock_db = MagicMock()
    mock_db.query.side_effect = Exception("db down")
    with patch("services.hfish_collector.SessionLocal", return_value=mock_db):
        hc._load_config()
    assert hc.enabled is False
    mock_db.close.assert_called_once()


def test_ensure_config_loaded_once():
    hc = HFishCollector()
    hc._config_loaded = True
    hc._load_config = MagicMock()
    hc._ensure_config_loaded()
    hc._load_config.assert_not_called()
