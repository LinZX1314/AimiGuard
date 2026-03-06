"""TD-05: 告警通道补全测试"""
import pytest


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_create_webhook_channel(client, admin_token):
    response = client.post("/api/v1/push/channels", json={
        "channel_type": "webhook",
        "channel_name": "test_webhook",
        "target": "https://httpbin.org/post",
        "config_json": '{"method": "POST", "headers": {"Content-Type": "application/json"}}',
        "enabled": 1
    }, headers=_h(admin_token))
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["channel_name"] == "test_webhook"


def test_create_wecom_channel(client, admin_token):
    response = client.post("/api/v1/push/channels", json={
        "channel_type": "wecom",
        "channel_name": "test_wecom",
        "target": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
        "enabled": 1
    }, headers=_h(admin_token))
    assert response.status_code == 200
    assert response.json()["code"] == 0


def test_create_duplicate_channel(client, admin_token):
    client.post("/api/v1/push/channels", json={
        "channel_type": "webhook",
        "channel_name": "duplicate_test",
        "target": "https://httpbin.org/post"
    }, headers=_h(admin_token))

    response = client.post("/api/v1/push/channels", json={
        "channel_type": "webhook",
        "channel_name": "duplicate_test",
        "target": "https://httpbin.org/post"
    }, headers=_h(admin_token))
    assert response.status_code == 400


def test_list_channels(client, admin_token):
    client.post("/api/v1/push/channels", json={
        "channel_type": "webhook",
        "channel_name": "list_test_1",
        "target": "https://httpbin.org/post"
    }, headers=_h(admin_token))
    client.post("/api/v1/push/channels", json={
        "channel_type": "wecom",
        "channel_name": "list_test_2",
        "target": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test"
    }, headers=_h(admin_token))

    response = client.get("/api/v1/push/channels", headers=_h(admin_token))
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert len(data["data"]) >= 2


def test_update_channel(client, admin_token):
    create_resp = client.post("/api/v1/push/channels", json={
        "channel_type": "webhook",
        "channel_name": "update_test",
        "target": "https://httpbin.org/post"
    }, headers=_h(admin_token))
    channel_id = create_resp.json()["data"]["id"]

    response = client.put(f"/api/v1/push/channels/{channel_id}", json={
        "target": "https://httpbin.org/anything",
        "enabled": 0
    }, headers=_h(admin_token))
    assert response.status_code == 200


def test_delete_channel(client, admin_token):
    create_resp = client.post("/api/v1/push/channels", json={
        "channel_type": "webhook",
        "channel_name": "delete_test",
        "target": "https://httpbin.org/post"
    }, headers=_h(admin_token))
    channel_id = create_resp.json()["data"]["id"]

    response = client.delete(f"/api/v1/push/channels/{channel_id}",
                             headers=_h(admin_token))
    assert response.status_code == 200

    get_resp = client.get("/api/v1/push/channels", headers=_h(admin_token))
    channels = get_resp.json()["data"]
    assert not any(c["id"] == channel_id for c in channels)


def test_test_webhook_channel(client, admin_token):
    create_resp = client.post("/api/v1/push/channels", json={
        "channel_type": "webhook",
        "channel_name": "test_webhook_push",
        "target": "https://httpbin.org/post",
        "config_json": '{"method": "POST"}'
    }, headers=_h(admin_token))
    channel_id = create_resp.json()["data"]["id"]

    response = client.post(f"/api/v1/push/channels/{channel_id}/test",
                           headers=_h(admin_token))
    assert response.status_code == 200


def test_test_nonexistent_channel(client, admin_token):
    response = client.post("/api/v1/push/channels/99999/test",
                           headers=_h(admin_token))
    assert response.status_code == 404


def test_invalid_channel_type(client, admin_token):
    response = client.post("/api/v1/push/channels", json={
        "channel_type": "invalid_type",
        "channel_name": "invalid_test",
        "target": "https://example.com"
    }, headers=_h(admin_token))
    assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
