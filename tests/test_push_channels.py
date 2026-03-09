"""Push service — unit tests for all 5 channel types + API CRUD."""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from core.database import PushChannel
from services.push_service import PushService


# ── helpers ──

def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_channel(db, *, channel_type="webhook", name="test-ch", target="http://127.0.0.1:65534/hook",
                  config_json=None, enabled=1) -> PushChannel:
    ch = PushChannel(
        channel_type=channel_type,
        channel_name=name,
        target=target,
        config_json=config_json,
        enabled=enabled,
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


# ── 1. Channel CRUD API ──

def test_create_channel(client, admin_token, db):
    resp = client.post("/api/v1/push/channels", json={
        "channel_type": "feishu",
        "channel_name": "feishu-sec-alert",
        "target": "https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
        "config_json": json.dumps({"secret": "test-secret"}),
    }, headers=_h(admin_token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] > 0
    assert data["channel_name"] == "feishu-sec-alert"


def test_create_channel_invalid_type(client, admin_token):
    resp = client.post("/api/v1/push/channels", json={
        "channel_type": "telegram",
        "channel_name": "bad-type",
        "target": "http://example.com",
    }, headers=_h(admin_token))
    assert resp.status_code == 400


def test_create_channel_duplicate_name(client, admin_token, db):
    _make_channel(db, name="dup-ch", channel_type="webhook")
    resp = client.post("/api/v1/push/channels", json={
        "channel_type": "webhook",
        "channel_name": "dup-ch",
        "target": "http://example.com",
    }, headers=_h(admin_token))
    assert resp.status_code == 400


def test_list_channels(client, admin_token, db):
    _make_channel(db, name="list-ch-1", channel_type="dingtalk")
    _make_channel(db, name="list-ch-2", channel_type="email", target="mailto:a@b.com")
    resp = client.get("/api/v1/push/channels", headers=_h(admin_token))
    assert resp.status_code == 200
    items = resp.json()["data"]
    names = {c["channel_name"] for c in items}
    assert "list-ch-1" in names
    assert "list-ch-2" in names


def test_update_channel(client, admin_token, db):
    ch = _make_channel(db, name="upd-ch", channel_type="wecom")
    resp = client.put(f"/api/v1/push/channels/{ch.id}", json={
        "channel_name": "upd-ch-renamed",
        "enabled": 0,
    }, headers=_h(admin_token))
    assert resp.status_code == 200
    db.refresh(ch)
    assert ch.channel_name == "upd-ch-renamed"
    assert ch.enabled == 0


def test_update_channel_not_found(client, admin_token):
    resp = client.put("/api/v1/push/channels/99999", json={
        "enabled": 0,
    }, headers=_h(admin_token))
    assert resp.status_code == 404


def test_delete_channel(client, admin_token, db):
    ch = _make_channel(db, name="del-ch", channel_type="webhook")
    ch_id = ch.id
    resp = client.delete(f"/api/v1/push/channels/{ch_id}", headers=_h(admin_token))
    assert resp.status_code == 200
    assert db.query(PushChannel).filter(PushChannel.id == ch_id).first() is None


def test_delete_channel_not_found(client, admin_token):
    resp = client.delete("/api/v1/push/channels/99999", headers=_h(admin_token))
    assert resp.status_code == 404


# ── 2. Disabled channel skip ──

@pytest.mark.asyncio
async def test_disabled_channel_returns_failed(db):
    ch = _make_channel(db, name="disabled-ch", enabled=0)
    result = await PushService.send(ch, "test", "trace-1")
    assert result["success"] is False
    assert result["detail"] == "channel_disabled"


# ── 3. Webhook channel ──

@pytest.mark.asyncio
async def test_webhook_post(db):
    ch = _make_channel(db, name="wh-post", channel_type="webhook",
                       target="http://127.0.0.1:65534/hook")
    mock_resp = MagicMock(status_code=200)
    with patch("services.push_service.httpx.AsyncClient") as mock_client_cls:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = instance
        result = await PushService._send_webhook(ch, "hello", "t-1")
    assert result["success"] is True
    assert result["response_status"] == 200


@pytest.mark.asyncio
async def test_webhook_get_method(db):
    ch = _make_channel(db, name="wh-get", channel_type="webhook",
                       config_json=json.dumps({"method": "GET"}))
    mock_resp = MagicMock(status_code=200)
    with patch("services.push_service.httpx.AsyncClient") as mock_client_cls:
        instance = AsyncMock()
        instance.get = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = instance
        result = await PushService._send_webhook(ch, "hello", "t-2")
    assert result["success"] is True
    instance.get.assert_called_once()


# ── 4. WeCom channel ──

@pytest.mark.asyncio
async def test_wecom_markdown(db):
    ch = _make_channel(db, name="wecom-md", channel_type="wecom",
                       target="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx")
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"errcode": 0, "errmsg": "ok"}
    with patch("services.push_service.httpx.AsyncClient") as mock_client_cls:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = instance
        result = await PushService._send_wecom(ch, "**告警**")
    assert result["success"] is True
    assert "errcode=0" in result["detail"]
    call_kwargs = instance.post.call_args
    payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert payload["msgtype"] == "markdown"


@pytest.mark.asyncio
async def test_wecom_text_mode(db):
    ch = _make_channel(db, name="wecom-txt", channel_type="wecom",
                       config_json=json.dumps({"markdown": False}))
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"errcode": 0}
    with patch("services.push_service.httpx.AsyncClient") as mock_client_cls:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = instance
        result = await PushService._send_wecom(ch, "plain text")
    assert result["success"] is True
    payload = instance.post.call_args.kwargs.get("json") or instance.post.call_args[1].get("json")
    assert payload["msgtype"] == "text"


@pytest.mark.asyncio
async def test_wecom_errcode_nonzero(db):
    ch = _make_channel(db, name="wecom-err", channel_type="wecom")
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"errcode": 93000, "errmsg": "invalid webhook url"}
    with patch("services.push_service.httpx.AsyncClient") as mock_client_cls:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = instance
        result = await PushService._send_wecom(ch, "msg")
    assert result["success"] is False
    assert "93000" in result["detail"]


# ── 5. DingTalk channel ──

@pytest.mark.asyncio
async def test_dingtalk_with_sign(db):
    ch = _make_channel(db, name="ding-sign", channel_type="dingtalk",
                       target="https://oapi.dingtalk.com/robot/send?access_token=xxx",
                       config_json=json.dumps({"secret": "SEC_test_key"}))
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"errcode": 0, "errmsg": "ok"}
    with patch("services.push_service.httpx.AsyncClient") as mock_client_cls:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = instance
        result = await PushService._send_dingtalk(ch, "**DingTalk告警**")
    assert result["success"] is True
    url_called = instance.post.call_args[0][0]
    assert "timestamp=" in url_called
    assert "sign=" in url_called


@pytest.mark.asyncio
async def test_dingtalk_without_sign(db):
    ch = _make_channel(db, name="ding-nosign", channel_type="dingtalk",
                       target="https://oapi.dingtalk.com/robot/send?access_token=xxx")
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"errcode": 0}
    with patch("services.push_service.httpx.AsyncClient") as mock_client_cls:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = instance
        result = await PushService._send_dingtalk(ch, "msg")
    assert result["success"] is True
    url_called = instance.post.call_args[0][0]
    assert "timestamp=" not in url_called


def test_dingtalk_sign_format():
    ts, sign = PushService._dingtalk_sign("SEC_test")
    assert ts.isdigit()
    assert len(ts) == 13  # milliseconds
    assert len(sign) > 20  # base64 encoded


# ── 6. Feishu channel ──

@pytest.mark.asyncio
async def test_feishu_interactive_card(db):
    ch = _make_channel(db, name="feishu-card", channel_type="feishu",
                       target="https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
                       config_json=json.dumps({"secret": "feishu_secret_123"}))
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"code": 0, "msg": "success"}
    with patch("services.push_service.httpx.AsyncClient") as mock_client_cls:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = instance
        result = await PushService._send_feishu(ch, "**安全告警**: 检测到暴力破解")
    assert result["success"] is True
    assert "feishu_code=0" in result["detail"]
    payload = instance.post.call_args.kwargs.get("json") or instance.post.call_args[1].get("json")
    assert payload["msg_type"] == "interactive"
    assert "timestamp" in payload
    assert "sign" in payload
    assert payload["card"]["header"]["template"] == "red"


@pytest.mark.asyncio
async def test_feishu_text_mode(db):
    ch = _make_channel(db, name="feishu-txt", channel_type="feishu",
                       config_json=json.dumps({"rich": False}))
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"code": 0}
    with patch("services.push_service.httpx.AsyncClient") as mock_client_cls:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = instance
        result = await PushService._send_feishu(ch, "plain text alert")
    assert result["success"] is True
    payload = instance.post.call_args.kwargs.get("json") or instance.post.call_args[1].get("json")
    assert payload["msg_type"] == "text"
    assert payload["content"]["text"] == "plain text alert"


@pytest.mark.asyncio
async def test_feishu_no_sign(db):
    ch = _make_channel(db, name="feishu-nosign", channel_type="feishu")
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"code": 0}
    with patch("services.push_service.httpx.AsyncClient") as mock_client_cls:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = instance
        result = await PushService._send_feishu(ch, "msg")
    assert result["success"] is True
    payload = instance.post.call_args.kwargs.get("json") or instance.post.call_args[1].get("json")
    assert "timestamp" not in payload
    assert "sign" not in payload


@pytest.mark.asyncio
async def test_feishu_nonzero_code(db):
    ch = _make_channel(db, name="feishu-fail", channel_type="feishu")
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"code": 19021, "msg": "sign match fail or timestamp is not within one hour from current time"}
    with patch("services.push_service.httpx.AsyncClient") as mock_client_cls:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = instance
        result = await PushService._send_feishu(ch, "msg")
    assert result["success"] is False
    assert "19021" in result["detail"]


def test_feishu_sign_format():
    ts, sign = PushService._feishu_sign("test_secret")
    assert ts.isdigit()
    assert len(ts) == 10  # seconds (not ms)
    assert len(sign) > 20  # base64


# ── 7. Email channel ──

@pytest.mark.asyncio
async def test_email_no_smtp_host(db):
    ch = _make_channel(db, name="email-nohost", channel_type="email",
                       target="mailto:admin@example.com")
    result = await PushService._send_email(ch, "alert", "t-1")
    assert result["success"] is False
    assert "smtp_not_configured" in result["detail"]


@pytest.mark.asyncio
async def test_email_empty_target(db):
    ch = _make_channel(db, name="email-empty", channel_type="email", target="mailto:")
    result = await PushService._send_email(ch, "alert", "t-1")
    assert result["success"] is False
    assert "email_target_empty" in result["detail"]


@pytest.mark.asyncio
async def test_email_smtp_success(db, monkeypatch):
    ch = _make_channel(db, name="email-ok", channel_type="email",
                       target="mailto:sec@company.com",
                       config_json=json.dumps({
                           "smtp_host": "smtp.example.com",
                           "smtp_port": 587,
                           "smtp_user": "bot@example.com",
                           "smtp_password": "pass123",
                           "smtp_tls": True,
                       }))
    mock_smtp = MagicMock()
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)
    with patch("services.push_service.smtplib.SMTP", return_value=mock_smtp):
        result = await PushService._send_email(ch, "安全告警: 检测到异常", "t-email")
    assert result["success"] is True
    assert result["response_status"] == 250
    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once_with("bot@example.com", "pass123")
    mock_smtp.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_email_smtp_failure(db):
    ch = _make_channel(db, name="email-fail", channel_type="email",
                       target="mailto:admin@example.com",
                       config_json=json.dumps({"smtp_host": "bad.host.invalid"}))
    result = await PushService._send_email(ch, "msg", "t-3")
    assert result["success"] is False
    assert "smtp_error" in result["detail"]


# ── 8. Dispatch & unsupported type ──

@pytest.mark.asyncio
async def test_dispatch_unsupported_type(db):
    ch = _make_channel(db, name="bad-type-ch", channel_type="telegram")
    result = await PushService.send(ch, "msg", "t-u")
    assert result["success"] is False
    assert "unsupported_channel_type" in result["detail"]


# ── 9. Alert message formatting ──

def test_format_alert_message():
    msg = PushService.format_alert_message(
        title="暴力破解告警",
        severity="CRITICAL",
        ip="10.0.0.1",
        source="HFish",
        summary="SSH暴力破解 50次/分钟",
        event_id=42,
        extra={"蜜罐": "ssh-honeypot-01"},
    )
    assert "🔴" in msg
    assert "暴力破解告警" in msg
    assert "10.0.0.1" in msg
    assert "HFish" in msg
    assert "42" in msg
    assert "ssh-honeypot-01" in msg
    assert "Aimiguan" in msg


def test_format_alert_severity_colors():
    for sev, emoji in [("CRITICAL", "🔴"), ("HIGH", "🟠"), ("MEDIUM", "🟡"), ("LOW", "🟢")]:
        msg = PushService.format_alert_message(severity=sev)
        assert emoji in msg


# ── 10. Test channel API ──

def test_test_channel_not_found(client, admin_token):
    resp = client.post("/api/v1/push/channels/99999/test", headers=_h(admin_token))
    assert resp.status_code == 404


def test_test_channel_sandbox(client, admin_token, db, monkeypatch):
    monkeypatch.setenv("PUSH_SANDBOX_MODE", "1")
    ch = _make_channel(db, name="test-sandbox-ch", channel_type="dingtalk",
                       target="https://oapi.dingtalk.com/robot/send?access_token=xxx")
    resp = client.post(f"/api/v1/push/channels/{ch.id}/test", headers=_h(admin_token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["simulated"] is True
    assert data["status"] == "simulated_success"
