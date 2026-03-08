"""D2-02 AI蜜罐自适应 + D2-03 Honeytoken生命周期 测试"""
import pytest
from starlette.testclient import TestClient


# ── D2-02: suggest_honeypot_strategy ──

def test_suggest_strategy_with_ssh_trend():
    """SSH攻击趋势应推荐SSH蜜罐"""
    import asyncio
    from services.ai_engine import ai_engine

    trend = {
        "top_attack_types": [{"type": "ssh_brute_force", "count": 100}],
        "total_events": 100,
    }
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(ai_engine.suggest_honeypot_strategy(trend))
    finally:
        loop.close()

    assert result["total_suggestions"] >= 1
    assert any(s["honeypot_type"] == "ssh" for s in result["suggestions"])


def test_suggest_strategy_empty():
    """无攻击趋势时应无建议"""
    import asyncio
    from services.ai_engine import ai_engine

    trend = {"top_attack_types": [], "total_events": 0}
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(ai_engine.suggest_honeypot_strategy(trend))
    finally:
        loop.close()

    assert result["total_suggestions"] == 0


def test_suggest_strategy_api(client: TestClient, admin_token: str):
    """GET /honeypots/strategy/suggest 应返回策略建议"""
    res = client.get(
        "/api/v1/honeypots/strategy/suggest",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert "suggestions" in data
    assert "total_suggestions" in data


# ── D2-03: Honeytoken 生命周期 ──

def test_generate_honeytoken(client: TestClient, admin_token: str):
    """生成蜜标应返回原始值和哈希"""
    res = client.post(
        "/api/v1/honeytokens/generate",
        json={"token_type": "api_key", "deployed_location": "/etc/config"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["token_type"] == "api_key"
    assert data["status"] == "ACTIVE"
    assert "raw_value" in data
    assert data["raw_value"].startswith("sk-honey-")
    assert data["value_hash"] is not None


def test_generate_credential_honeytoken(client: TestClient, admin_token: str):
    """生成credential蜜标"""
    res = client.post(
        "/api/v1/honeytokens/generate",
        json={"token_type": "credential"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert ":" in data["raw_value"]


def test_list_honeytokens(client: TestClient, admin_token: str):
    """列表查询蜜标"""
    client.post(
        "/api/v1/honeytokens/generate",
        json={"token_type": "api_key"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    res = client.get(
        "/api/v1/honeytokens",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["total"] == 1


def test_trigger_honeytoken_creates_alert(client: TestClient, admin_token: str):
    """蜜标触发应创建高置信度告警"""
    gen_res = client.post(
        "/api/v1/honeytokens/generate",
        json={"token_type": "api_key"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    raw_value = (gen_res.json().get("data") or gen_res.json())["raw_value"]

    res = client.post(
        "/api/v1/honeytokens/trigger",
        json={"value": raw_value, "attacker_ip": "192.168.1.100"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["status"] == "TRIGGERED"
    assert data["ai_score"] == 95
    assert data["threat_event_id"] is not None


def test_trigger_invalid_honeytoken(client: TestClient):
    """无效蜜标触发应404"""
    res = client.post(
        "/api/v1/honeytokens/trigger",
        json={"value": "fake-invalid-token"},
    )
    assert res.status_code == 404
