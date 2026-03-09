"""middleware/ip_whitelist.py tests — network parsing, client IP, whitelist dispatch."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from middleware.ip_whitelist import (
    _parse_networks,
    _get_client_ip,
    IPWhitelistMiddleware,
    ALWAYS_ALLOW_PATHS,
)


# ── _parse_networks ──

def test_parse_single_cidr():
    nets = _parse_networks("10.0.0.0/8")
    assert len(nets) == 1


def test_parse_multiple_cidrs():
    nets = _parse_networks("10.0.0.0/8, 192.168.0.0/16, 172.16.0.0/12")
    assert len(nets) == 3


def test_parse_empty():
    nets = _parse_networks("")
    assert nets == []


def test_parse_invalid_skipped():
    nets = _parse_networks("10.0.0.0/8, not_valid, 192.168.0.0/16")
    assert len(nets) == 2


def test_parse_single_ip():
    nets = _parse_networks("10.0.0.1")
    assert len(nets) == 1


# ── _get_client_ip ──

def test_get_client_ip_forwarded():
    request = MagicMock()
    request.headers.get.return_value = "1.2.3.4, 5.6.7.8"
    assert _get_client_ip(request) == "1.2.3.4"


def test_get_client_ip_direct():
    request = MagicMock()
    request.headers.get.return_value = None
    request.client.host = "10.0.0.1"
    assert _get_client_ip(request) == "10.0.0.1"


def test_get_client_ip_no_client():
    request = MagicMock()
    request.headers.get.return_value = None
    request.client = None
    assert _get_client_ip(request) == "0.0.0.0"


# ── IPWhitelistMiddleware ──

def test_middleware_disabled_when_empty():
    with patch.dict("os.environ", {"IP_WHITELIST": ""}, clear=False):
        mw = IPWhitelistMiddleware(MagicMock())
    assert mw.enabled is False


def test_middleware_enabled_with_env():
    with patch.dict("os.environ", {"IP_WHITELIST": "10.0.0.0/8"}, clear=False):
        mw = IPWhitelistMiddleware(MagicMock())
    assert mw.enabled is True
    assert len(mw.networks) == 1


def test_middleware_enabled_with_explicit_list():
    mw = IPWhitelistMiddleware(MagicMock(), whitelist=["192.168.1.0/24"])
    assert mw.enabled is True


def test_is_whitelisted_match():
    mw = IPWhitelistMiddleware(MagicMock(), whitelist=["10.0.0.0/8"])
    assert mw._is_whitelisted("10.1.2.3") is True


def test_is_whitelisted_no_match():
    mw = IPWhitelistMiddleware(MagicMock(), whitelist=["10.0.0.0/8"])
    assert mw._is_whitelisted("192.168.1.1") is False


def test_is_whitelisted_invalid_ip():
    mw = IPWhitelistMiddleware(MagicMock(), whitelist=["10.0.0.0/8"])
    assert mw._is_whitelisted("not_an_ip") is False


# ── dispatch ──

@pytest.mark.asyncio
async def test_dispatch_disabled_passes_through():
    with patch.dict("os.environ", {"IP_WHITELIST": ""}, clear=False):
        mw = IPWhitelistMiddleware(MagicMock())
    request = MagicMock()
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    resp = await mw.dispatch(request, call_next)
    call_next.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_always_allow_paths():
    mw = IPWhitelistMiddleware(MagicMock(), whitelist=["10.0.0.0/8"])
    request = MagicMock()
    request.url.path = "/api/health"
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    resp = await mw.dispatch(request, call_next)
    call_next.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_whitelisted_ip_passes():
    mw = IPWhitelistMiddleware(MagicMock(), whitelist=["10.0.0.0/8"])
    request = MagicMock()
    request.url.path = "/api/scan"
    request.headers.get.return_value = None
    request.client.host = "10.0.0.5"
    request.method = "GET"
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    resp = await mw.dispatch(request, call_next)
    call_next.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_blocked_ip_returns_404():
    mw = IPWhitelistMiddleware(MagicMock(), whitelist=["10.0.0.0/8"])
    request = MagicMock()
    request.url.path = "/api/scan"
    request.headers.get.return_value = None
    request.client.host = "192.168.1.1"
    request.method = "GET"
    call_next = AsyncMock()
    resp = await mw.dispatch(request, call_next)
    assert resp.status_code == 404
    call_next.assert_not_awaited()
