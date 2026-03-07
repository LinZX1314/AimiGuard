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
