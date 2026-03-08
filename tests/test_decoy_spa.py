"""
蜜罐端点与伪装路由 + SPA 单包授权 集成测试

验证：
  1. 蜜罐端点在 DECOY_ENABLED=false 时返回 404
  2. 蜜罐端点在 DECOY_ENABLED=true 时正常诱捕
  3. SPA 令牌生成与验证
  4. IP 白名单中间件逻辑
"""
import hashlib
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


# ---------------------------------------------------------------------------
# 1. 蜜罐端点（默认关闭）
# ---------------------------------------------------------------------------

class TestDecoyEndpointsDisabled:
    """DECOY_ENABLED=false 时蜜罐端点应返回 404"""

    def test_admin_login_404_when_disabled(self, client):
        resp = client.get("/admin/login")
        assert resp.status_code == 404

    def test_admin_auth_404_when_disabled(self, client):
        resp = client.post("/admin/auth", data={"username": "hacker", "password": "pass"})
        assert resp.status_code == 404

    def test_fake_users_api_404_when_disabled(self, client):
        resp = client.get("/api/v1/users/list")
        assert resp.status_code in (401, 404)

    def test_env_file_404_when_disabled(self, client):
        resp = client.get("/.env")
        assert resp.status_code == 404

    def test_wp_admin_404_when_disabled(self, client):
        resp = client.get("/wp-admin")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 2. 蜜罐端点（启用时） — 通过 monkeypatch 模拟
# ---------------------------------------------------------------------------

class TestDecoyEndpointsEnabled:
    """DECOY_ENABLED=true 时蜜罐端点应正常工作"""

    @pytest.fixture(autouse=True)
    def enable_decoy(self, monkeypatch):
        import api.decoy as decoy_mod
        monkeypatch.setattr(decoy_mod, "DECOY_ENABLED", True)

    def test_admin_login_returns_html(self, client):
        resp = client.get("/admin/login")
        assert resp.status_code == 200
        assert "Admin Panel" in resp.text
        assert "<form" in resp.text

    def test_admin_auth_delays_and_rejects(self, client):
        start = time.time()
        resp = client.post(
            "/admin/auth",
            data={"username": "attacker", "password": "password123"},
        )
        elapsed = time.time() - start
        assert resp.status_code == 401
        assert "Invalid credentials" in resp.text
        # 应有延迟（至少 2 秒，正常 3 秒）
        assert elapsed >= 2.0, f"Decoy auth should delay, but took {elapsed:.1f}s"

    def test_fake_users_returns_fake_data(self, client):
        resp = client.get("/api/v1/users/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert len(data["users"]) >= 1

    def test_env_file_returns_403(self, client):
        resp = client.get("/.env")
        assert resp.status_code == 403

    def test_wp_admin_returns_404_html(self, client):
        resp = client.get("/wp-admin")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3. SPA 单包授权
# ---------------------------------------------------------------------------

class TestSPAIntegration:
    """SPA 令牌生成、验证、边界情况"""

    def test_roundtrip(self):
        from services.spa_service import generate_spa_token, verify_spa_token
        secret = "integration-test-secret-32chars!!"
        token = generate_spa_token("192.168.1.100", secret)
        ok, reason = verify_spa_token(token, "192.168.1.100", secret)
        assert ok is True

    def test_token_format(self):
        from services.spa_service import generate_spa_token
        token = generate_spa_token("10.0.0.1", "secret")
        parts = token.split(":")
        assert len(parts) == 3  # ip:timestamp:signature
        assert parts[0] == "10.0.0.1"
        assert parts[1].isdigit()
        assert len(parts[2]) == 64  # SHA256 hex

    def test_replay_with_different_ip_fails(self):
        from services.spa_service import generate_spa_token, verify_spa_token
        secret = "test"
        token = generate_spa_token("10.0.0.1", secret)
        ok, _ = verify_spa_token(token, "10.0.0.2", secret)
        assert ok is False

    def test_no_secret_raises(self):
        from services.spa_service import generate_spa_token
        with pytest.raises(ValueError):
            generate_spa_token("10.0.0.1", "")


# ---------------------------------------------------------------------------
# 4. IP 白名单中间件逻辑
# ---------------------------------------------------------------------------

class TestIPWhitelistLogic:
    """IP 白名单核心逻辑"""

    def test_cidr_matching(self):
        from middleware.ip_whitelist import IPWhitelistMiddleware
        mw = IPWhitelistMiddleware(app=None, whitelist=["192.168.1.0/24"])
        assert mw._is_whitelisted("192.168.1.1") is True
        assert mw._is_whitelisted("192.168.1.254") is True
        assert mw._is_whitelisted("192.168.2.1") is False

    def test_localhost_always_configurable(self):
        from middleware.ip_whitelist import IPWhitelistMiddleware
        mw = IPWhitelistMiddleware(app=None, whitelist=["127.0.0.0/8"])
        assert mw._is_whitelisted("127.0.0.1") is True

    def test_disabled_when_empty(self):
        from middleware.ip_whitelist import IPWhitelistMiddleware
        mw = IPWhitelistMiddleware(app=None, whitelist=[])
        assert mw.enabled is False
