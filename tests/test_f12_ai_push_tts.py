import pytest
from sqlalchemy import text


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_ai_chat_returns_meta(client, admin_token, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:65534")

    resp = client.post(
        "/api/v1/ai/chat",
        json={"message": "请分析当前告警"},
        headers=_h(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert isinstance(data.get("message"), str) and data["message"]
    assert "meta" in data
    assert "trace_id" in data["meta"]
    assert data["meta"]["trace_id"] == body["trace_id"]
    assert isinstance(data["meta"].get("degraded"), bool)


def test_report_generate_returns_meta(client, admin_token, db):
    db.execute(
        text(
            """
            INSERT OR IGNORE INTO permission (name, resource, action, description, created_at)
            VALUES ('generate_report', 'report', 'generate', 'Generate security reports', datetime('now'))
            """
        )
    )
    db.execute(
        text(
            """
            INSERT OR IGNORE INTO role_permission (role_id, permission_id, created_at)
            SELECT 1, id, datetime('now') FROM permission WHERE name = 'generate_report'
            """
        )
    )
    db.commit()

    resp = client.post(
        "/api/v1/report/generate",
        json={"report_type": "daily", "scope": "global"},
        headers=_h(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["report_id"] > 0
    assert data["detail_path"].startswith("/generated_reports/")
    assert "meta" in data
    assert data["meta"]["trace_id"] == body["trace_id"]


def test_push_test_channel_uses_sandbox_mode(client, admin_token, monkeypatch):
    monkeypatch.setenv("PUSH_SANDBOX_MODE", "1")

    create_resp = client.post(
        "/api/v1/push/channels",
        json={
            "channel_type": "webhook",
            "channel_name": "f12_push_sandbox",
            "target": "http://127.0.0.1:65534/webhook",
            "enabled": 1,
        },
        headers=_h(admin_token),
    )
    assert create_resp.status_code == 200
    channel_id = create_resp.json()["data"]["id"]

    test_resp = client.post(
        f"/api/v1/push/channels/{channel_id}/test",
        headers=_h(admin_token),
    )
    assert test_resp.status_code == 200
    body = test_resp.json()
    assert body["code"] == 0
    assert body["data"]["simulated"] is True
    assert body["data"]["status"] == "simulated_success"


@pytest.mark.asyncio
async def test_push_send_alert_bypasses_sandbox_mode(db, monkeypatch):
    from core.database import PushChannel
    from services.push_service import PushService

    monkeypatch.setenv("PUSH_SANDBOX_MODE", "1")

    channel = PushChannel(
        channel_type="webhook",
        channel_name="f12_real_alert",
        target="http://127.0.0.1:65534/webhook",
        enabled=1,
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    called = {"value": False}

    async def fake_send_webhook(channel_obj, message, trace_id):
        called["value"] = True
        return {
            "success": True,
            "status": "success",
            "detail": "ok",
            "response_status": 200,
            "simulated": False,
        }

    monkeypatch.setattr(PushService, "_send_webhook", staticmethod(fake_send_webhook))

    def _session_factory():
        return db.__class__(bind=db.get_bind())

    results = await PushService.send_alert(
        _session_factory,
        title="真实告警",
        severity="HIGH",
        ip="1.2.3.4",
        source="unit_test",
        summary="sandbox should be bypassed",
        event_id=1,
        trace_id="trace-real-alert",
    )

    assert called["value"] is True
    assert len(results) == 1
    assert results[0]["success"] is True
    assert results[0]["simulated"] is False


def test_defense_alert_schedules_push_for_high_ai_score(client, monkeypatch):
    from api import defense as defense_api

    scheduled = {"called": False}

    async def fake_assess_threat(ip, attack_type, attack_count, history=None):
        return {
            "score": 95,
            "reason": "high_risk",
            "action_suggest": "BLOCK",
        }

    def fake_ensure_future(coro):
        scheduled["called"] = True
        coro.close()
        return None

    monkeypatch.setattr(defense_api.ai_engine, "assess_threat", fake_assess_threat)
    monkeypatch.setattr(defense_api.asyncio, "ensure_future", fake_ensure_future)

    response = client.post(
        "/api/v1/defense/alerts",
        json={
            "response_code": 0,
            "response_message": "ok",
            "list_infos": [
                {
                    "client_id": "push-trigger-high-score",
                    "service_name": "ssh-honeypot",
                    "service_type": "ssh",
                    "attack_ip": "5.6.7.8",
                    "attack_count": 5,
                    "labels": "ssh-brute",
                }
            ],
            "attack_infos": [],
            "attack_trend": [],
        },
    )

    assert response.status_code == 200
    assert scheduled["called"] is True


def test_tts_process_uses_sandbox_mode(client, admin_token, monkeypatch):
    monkeypatch.setenv("TTS_SANDBOX_MODE", "1")

    create_resp = client.post(
        "/api/v1/tts/tasks",
        json={"text": "f12 tts sandbox", "voice_model": "local-tts-v1"},
        headers=_h(admin_token),
    )
    assert create_resp.status_code == 200
    task_id = create_resp.json()["data"]["task_id"]

    process_resp = client.post(
        f"/api/v1/tts/tasks/{task_id}/process",
        headers=_h(admin_token),
    )
    assert process_resp.status_code == 200
    body = process_resp.json()
    assert body["code"] == 0
    assert body["data"]["state"] == "SUCCESS"
    assert body["data"]["simulated"] is True
    assert isinstance(body["data"]["audio_path"], str) and body["data"]["audio_path"]
