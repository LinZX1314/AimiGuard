"""S2-01 MCP插件来源验证与签名校验 测试"""
import pytest
from starlette.testclient import TestClient


# ── plugin_security 服务逻辑 ──

def test_verify_safe_plugin():
    """合法插件应通过验证"""
    from services.plugin_security import verify_plugin
    is_safe, risk_level, reason = verify_plugin(
        plugin_name="good-plugin",
        source_url="https://github.com/org/good-plugin",
    )
    assert is_safe is True
    assert reason == "verification_passed"


def test_verify_blacklisted_source():
    """黑名单来源应被拒绝"""
    from services.plugin_security import verify_plugin
    is_safe, risk_level, reason = verify_plugin(
        plugin_name="evil",
        source_url="https://malicious-mcp-server.example.com/plugin",
    )
    assert is_safe is False
    assert risk_level == "critical"
    assert "blacklisted" in reason


def test_verify_missing_url():
    """无来源URL应被拒绝"""
    from services.plugin_security import verify_plugin
    is_safe, risk_level, reason = verify_plugin(
        plugin_name="no-url",
        source_url="",
    )
    assert is_safe is False


def test_verify_invalid_url_format():
    """无效URL格式应被拒绝"""
    from services.plugin_security import verify_plugin
    is_safe, risk_level, reason = verify_plugin(
        plugin_name="bad-url",
        source_url="ftp://not-http.com/plugin",
    )
    assert is_safe is False
    assert "invalid_format" in reason


def test_verify_with_valid_signature():
    """有效签名应通过"""
    from services.plugin_security import verify_plugin, compute_signature, compute_content_hash
    content = b"plugin content bytes"
    sig = compute_signature(content)
    h = compute_content_hash(content)

    is_safe, risk_level, reason = verify_plugin(
        plugin_name="signed-plugin",
        source_url="https://registry.example.com/signed",
        publisher_signature=sig,
        content_hash=h,
        plugin_content=content,
    )
    assert is_safe is True
    assert risk_level == "low"


def test_verify_with_wrong_signature():
    """错误签名应被拒绝"""
    from services.plugin_security import verify_plugin
    is_safe, risk_level, reason = verify_plugin(
        plugin_name="bad-sig",
        source_url="https://registry.example.com/bad",
        publisher_signature="hmac:0000000000000000000000000000000000000000000000000000000000000000",
        plugin_content=b"content",
    )
    assert is_safe is False
    assert "signature" in reason


def test_verify_hash_mismatch():
    """哈希不匹配应被拒绝"""
    from services.plugin_security import verify_plugin, compute_signature
    content = b"real content"
    sig = compute_signature(content)
    is_safe, risk_level, reason = verify_plugin(
        plugin_name="hash-mismatch",
        source_url="https://registry.example.com/hm",
        publisher_signature=sig,
        content_hash="0000000000000000000000000000000000000000000000000000000000000000",
        plugin_content=content,
    )
    assert is_safe is False
    assert "hash_mismatch" in reason


def test_blacklist_management():
    """黑名单增删"""
    from services.plugin_security import add_to_blacklist, remove_from_blacklist, get_blacklist
    add_to_blacklist("test-evil.com")
    assert "test-evil.com" in get_blacklist()
    remove_from_blacklist("test-evil.com")
    assert "test-evil.com" not in get_blacklist()


# ── API 集成 ──

def test_register_mcp_plugin_blacklisted(client: TestClient, admin_token: str):
    """注册黑名单MCP插件应被403拒绝"""
    res = client.post(
        "/api/v1/plugins",
        json={
            "plugin_name": "evil-mcp",
            "plugin_type": "mcp",
            "source_url": "https://malicious-mcp-server.example.com/evil",
            "endpoint": "stdio",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 403


def test_register_safe_mcp_plugin(client: TestClient, admin_token: str):
    """注册安全MCP插件应成功"""
    res = client.post(
        "/api/v1/plugins",
        json={
            "plugin_name": "safe-mcp",
            "plugin_type": "mcp",
            "source_url": "https://github.com/safe-org/plugin",
            "endpoint": "stdio",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200


def test_verify_endpoint(client: TestClient, admin_token: str):
    """POST /plugins/verify 预检验"""
    res = client.post(
        "/api/v1/plugins/verify",
        json={
            "plugin_name": "check-plugin",
            "plugin_type": "mcp",
            "source_url": "https://safe.example.com/plugin",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["is_safe"] is True


def test_blacklist_endpoint(client: TestClient, admin_token: str):
    """GET /plugins/blacklist 应返回黑名单"""
    res = client.get(
        "/api/v1/plugins/blacklist",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert "blacklist" in data
    assert len(data["blacklist"]) >= 1
