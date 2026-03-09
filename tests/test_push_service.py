"""PushService tests — dispatch, channels, sandbox, retry, formatting, email."""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from services.push_service import PushService, _bool_env


# ── helpers ──

def _make_channel(**overrides):
    ch = MagicMock()
    ch.id = overrides.get("id", 1)
    ch.channel_name = overrides.get("channel_name", "test_ch")
    ch.channel_type = overrides.get("channel_type", "webhook")
    ch.target = overrides.get("target", "http://hook.local/notify")
    ch.enabled = overrides.get("enabled", True)
    ch.config_json = overrides.get("config_json", None)
    return ch


# ── _bool_env ──

def test_bool_env_default():
    os.environ.pop("PUSH_TEST_X", None)
    assert _bool_env("PUSH_TEST_X", True) is True
    assert _bool_env("PUSH_TEST_X", False) is False


def test_bool_env_truthy():
    for val in ("1", "true", "yes", "on", "TRUE"):
        with patch.dict(os.environ, {"PUSH_TEST_X": val}):
            assert _bool_env("PUSH_TEST_X", False) is True


def test_bool_env_falsy():
    with patch.dict(os.environ, {"PUSH_TEST_X": "0"}):
        assert _bool_env("PUSH_TEST_X", True) is False


# ── sandbox_mode ──

def test_sandbox_mode_default():
    os.environ.pop("PUSH_SANDBOX_MODE", None)
    assert PushService.sandbox_mode() is False


def test_sandbox_mode_on():
    with patch.dict(os.environ, {"PUSH_SANDBOX_MODE": "1"}):
        assert PushService.sandbox_mode() is True


# ── _parse_config ──

def test_parse_config_none():
    ch = _make_channel(config_json=None)
    assert PushService._parse_config(ch) == {}


def test_parse_config_valid():
    ch = _make_channel(config_json='{"key": "val"}')
    assert PushService._parse_config(ch) == {"key": "val"}


def test_parse_config_invalid_json():
    ch = _make_channel(config_json="not json")
    assert PushService._parse_config(ch) == {}


def test_parse_config_non_dict():
    ch = _make_channel(config_json='[1,2]')
    assert PushService._parse_config(ch) == {}


# ── _dispatch_channel: disabled ──

@pytest.mark.asyncio
async def test_dispatch_disabled_channel():
    ch = _make_channel(enabled=False)
    result = await PushService._dispatch_channel(ch, "msg", "tr1", allow_sandbox=False)
    assert result["success"] is False
    assert result["detail"] == "channel_disabled"


# ── _dispatch_channel: sandbox ──

@pytest.mark.asyncio
async def test_dispatch_sandbox():
    ch = _make_channel()
    with patch.dict(os.environ, {"PUSH_SANDBOX_MODE": "1"}):
        result = await PushService._dispatch_channel(ch, "msg", "tr1", allow_sandbox=True)
    assert result["success"] is True
    assert result["simulated"] is True
    assert result["status"] == "simulated_success"


@pytest.mark.asyncio
async def test_dispatch_sandbox_not_allowed():
    ch = _make_channel()
    with patch.dict(os.environ, {"PUSH_SANDBOX_MODE": "1"}):
        with patch.object(PushService, "_send_webhook", new_callable=AsyncMock, return_value={"success": True, "status": "success", "detail": "ok", "response_status": 200, "simulated": False}):
            result = await PushService._dispatch_channel(ch, "msg", "tr1", allow_sandbox=False)
    assert result["simulated"] is False


# ── _dispatch_channel: unsupported type ──

@pytest.mark.asyncio
async def test_dispatch_unsupported_type():
    ch = _make_channel(channel_type="sms")
    result = await PushService._dispatch_channel(ch, "msg", "tr1", allow_sandbox=False)
    assert result["success"] is False
    assert "unsupported" in result["detail"]


# ── _dispatch_channel: exception ──

@pytest.mark.asyncio
async def test_dispatch_exception():
    ch = _make_channel(channel_type="webhook")
    with patch.object(PushService, "_send_webhook", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
        result = await PushService._dispatch_channel(ch, "msg", "tr1", allow_sandbox=False)
    assert result["success"] is False
    assert "RuntimeError" in result["detail"]


# ── format_alert_message ──

def test_format_alert_message_basic():
    msg = PushService.format_alert_message(
        title="test",
        severity="HIGH",
        ip="10.0.0.1",
        source="hfish",
        summary="brute force",
        event_id=42,
    )
    assert "10.0.0.1" in msg
    assert "test" in msg
    assert "HIGH" in msg
    assert "42" in msg


def test_format_alert_message_extra():
    msg = PushService.format_alert_message(
        severity="LOW",
        extra={"custom_key": "custom_value"},
    )
    assert "custom_key" in msg
    assert "custom_value" in msg


def test_format_alert_severity_emoji():
    msg = PushService.format_alert_message(severity="CRITICAL")
    assert "🔴" in msg


# ── _dingtalk_sign ──

def test_dingtalk_sign():
    ts, sign = PushService._dingtalk_sign("test_secret")
    assert ts.isdigit()
    assert len(sign) > 0


# ── _feishu_sign ──

def test_feishu_sign():
    ts, sign = PushService._feishu_sign("test_secret")
    assert ts.isdigit()
    assert len(sign) > 0


# ── _send_email_sync: no target ──

def test_email_empty_target():
    ch = _make_channel(channel_type="email", target="mailto:")
    result = PushService._send_email_sync(ch, "msg", "tr1")
    assert result["success"] is False
    assert "empty" in result["detail"]


def test_email_no_smtp():
    ch = _make_channel(channel_type="email", target="mailto:a@b.com", config_json='{}')
    with patch.dict(os.environ, {"PUSH_SMTP_HOST": ""}):
        result = PushService._send_email_sync(ch, "msg", "tr1")
    assert result["success"] is False
    assert "smtp_not_configured" in result["detail"]


# ── _write_push_log ──

def test_write_push_log_success():
    ch = _make_channel()
    mock_db = MagicMock()
    mock_log = MagicMock()
    mock_log.id = 99
    mock_db.add = MagicMock()
    mock_db.commit = MagicMock()
    with patch("services.push_service.PushLog", return_value=mock_log):
        log_id = PushService._write_push_log(
            mock_db,
            channel=ch,
            message="test",
            result={"success": True, "status": "success", "detail": "ok"},
            trace_id="tr1",
        )
    assert log_id == 99
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


def test_write_push_log_db_error():
    ch = _make_channel()
    mock_db = MagicMock()
    mock_db.add.side_effect = Exception("db fail")
    log_id = PushService._write_push_log(
        mock_db,
        channel=ch,
        message="test",
        result={"success": False},
        trace_id="tr1",
    )
    assert log_id is None
    mock_db.rollback.assert_called_once()


# ── send / send_test ──

@pytest.mark.asyncio
async def test_send_calls_dispatch():
    ch = _make_channel()
    with patch.object(PushService, "_dispatch_channel", new_callable=AsyncMock, return_value={"success": True}) as mock_dispatch:
        result = await PushService.send(ch, "msg", "tr1")
    assert result["success"] is True
    mock_dispatch.assert_called_once_with(ch, "msg", "tr1", allow_sandbox=False)


@pytest.mark.asyncio
async def test_send_test_allows_sandbox():
    ch = _make_channel()
    with patch.object(PushService, "_dispatch_channel", new_callable=AsyncMock, return_value={"success": True}) as mock_dispatch:
        await PushService.send_test(ch, "msg", "tr1")
    mock_dispatch.assert_called_once_with(ch, "msg", "tr1", allow_sandbox=True)
