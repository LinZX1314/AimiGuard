"""core/middleware.py tests — RateLimitMiddleware, require_role."""
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException

from core.middleware import RateLimitMiddleware, require_role


# ── RateLimitMiddleware._is_limited ──

def test_rate_limit_under_limit():
    app = MagicMock()
    rl = RateLimitMiddleware(app, global_rpm=5, login_rpm=2)
    assert rl._is_limited("test:1", 5) is False


def test_rate_limit_hits_limit():
    app = MagicMock()
    rl = RateLimitMiddleware(app, global_rpm=3, login_rpm=2)
    for _ in range(3):
        rl._is_limited("key1", 3)
    assert rl._is_limited("key1", 3) is True


def test_rate_limit_different_keys_independent():
    app = MagicMock()
    rl = RateLimitMiddleware(app, global_rpm=2, login_rpm=2)
    rl._is_limited("a", 2)
    rl._is_limited("a", 2)
    assert rl._is_limited("a", 2) is True
    assert rl._is_limited("b", 2) is False


# ── RateLimitMiddleware._client_ip ──

def test_client_ip_forwarded():
    app = MagicMock()
    rl = RateLimitMiddleware(app)
    request = MagicMock()
    request.headers.get.return_value = "1.2.3.4, 5.6.7.8"
    assert rl._client_ip(request) == "1.2.3.4"


def test_client_ip_direct():
    app = MagicMock()
    rl = RateLimitMiddleware(app)
    request = MagicMock()
    request.headers.get.return_value = None
    request.client.host = "10.0.0.1"
    assert rl._client_ip(request) == "10.0.0.1"


def test_client_ip_no_client():
    app = MagicMock()
    rl = RateLimitMiddleware(app)
    request = MagicMock()
    request.headers.get.return_value = None
    request.client = None
    assert rl._client_ip(request) == "unknown"


# ── RateLimitMiddleware.dispatch ──

@pytest.mark.asyncio
async def test_dispatch_testing_mode_bypasses():
    app = MagicMock()
    rl = RateLimitMiddleware(app, global_rpm=1)
    request = MagicMock()
    call_next = AsyncMock()
    with patch.dict("os.environ", {"TESTING": "1"}):
        await rl.dispatch(request, call_next)
    call_next.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_login_rate_limited():
    app = MagicMock()
    rl = RateLimitMiddleware(app, global_rpm=100, login_rpm=1)
    request = MagicMock()
    request.headers.get.return_value = None
    request.client.host = "10.0.0.1"
    request.url.path = "/api/auth/login"
    request.method = "POST"
    call_next = AsyncMock()

    with patch.dict("os.environ", {}, clear=True):
        # First request should pass
        resp1 = await rl.dispatch(request, call_next)
        # Second should be rate-limited
        resp2 = await rl.dispatch(request, call_next)
    assert resp2.status_code == 429


@pytest.mark.asyncio
async def test_dispatch_global_rate_limited():
    app = MagicMock()
    rl = RateLimitMiddleware(app, global_rpm=1, login_rpm=5)
    request = MagicMock()
    request.headers.get.return_value = None
    request.client.host = "10.0.0.2"
    request.url.path = "/api/scan"
    request.method = "GET"
    call_next = AsyncMock()

    with patch.dict("os.environ", {}, clear=True):
        await rl.dispatch(request, call_next)
        resp = await rl.dispatch(request, call_next)
    assert resp.status_code == 429


# ── require_role ──

@pytest.mark.asyncio
async def test_require_role_allowed():
    @require_role("admin", "operator")
    async def handler(current_user=None):
        return "ok"

    user = MagicMock()
    user.role = "admin"
    result = await handler(current_user=user)
    assert result == "ok"


@pytest.mark.asyncio
async def test_require_role_denied():
    @require_role("admin")
    async def handler(current_user=None):
        return "ok"

    user = MagicMock()
    user.role = "viewer"
    with pytest.raises(HTTPException) as exc_info:
        await handler(current_user=user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_no_user():
    @require_role("admin")
    async def handler(current_user=None):
        return "ok"

    with pytest.raises(HTTPException) as exc_info:
        await handler(current_user=None)
    assert exc_info.value.status_code == 403
