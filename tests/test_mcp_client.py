"""MCPClient tests — mock mode, error classification, business methods."""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from services.mcp_client import MCPClient, _classify_error_retryable


# ── Error classification ──

def test_retryable_timeout():
    assert _classify_error_retryable("Connection timeout") is True


def test_retryable_network():
    assert _classify_error_retryable("Network unreachable") is True


def test_retryable_rate_limit():
    assert _classify_error_retryable("Rate limit exceeded") is True


def test_retryable_status_503():
    assert _classify_error_retryable("Service error", status_code=503) is True


def test_retryable_status_429():
    assert _classify_error_retryable("Too many", status_code=429) is True


def test_not_retryable_auth():
    assert _classify_error_retryable("Authentication failed") is False


def test_not_retryable_not_found():
    assert _classify_error_retryable("Resource not found") is False


def test_not_retryable_status_401():
    assert _classify_error_retryable("Unauthorized", status_code=401) is False


def test_not_retryable_status_400():
    assert _classify_error_retryable("Bad request error", status_code=400) is False


def test_not_retryable_invalid():
    assert _classify_error_retryable("Invalid parameter") is False


def test_retryable_unknown_defaults_true():
    assert _classify_error_retryable("some random error") is True


# ── Mock mode ──

@pytest.mark.asyncio
async def test_mock_block_ip():
    with patch.dict(os.environ, {"MCP_MODE": "mock"}):
        client = MCPClient()
    result = await client.call_tool("block_ip", {"ip": "10.0.0.1", "device_id": 1})
    assert result["success"] is True
    assert result["result"]["action"] == "block"
    assert result["result"]["ip"] == "10.0.0.1"


@pytest.mark.asyncio
async def test_mock_unblock_ip():
    with patch.dict(os.environ, {"MCP_MODE": "mock"}):
        client = MCPClient()
    result = await client.call_tool("unblock_ip", {"ip": "10.0.0.1"})
    assert result["success"] is True
    assert result["result"]["action"] == "unblock"


@pytest.mark.asyncio
async def test_mock_get_device_status():
    with patch.dict(os.environ, {"MCP_MODE": "mock"}):
        client = MCPClient()
    result = await client.call_tool("get_device_status", {"device_id": 1})
    assert result["success"] is True
    assert result["result"]["status"] == "online"


@pytest.mark.asyncio
async def test_mock_get_acl_rules():
    with patch.dict(os.environ, {"MCP_MODE": "mock"}):
        client = MCPClient()
    result = await client.call_tool("get_acl_rules", {"device_id": 1})
    assert result["success"] is True
    assert len(result["result"]["rules"]) == 2


@pytest.mark.asyncio
async def test_mock_unknown_tool():
    with patch.dict(os.environ, {"MCP_MODE": "mock"}):
        client = MCPClient()
    result = await client.call_tool("nonexistent_tool", {})
    assert result["success"] is False
    assert result["retryable"] is False


# ── Unsupported mode ──

@pytest.mark.asyncio
async def test_unsupported_mode_raises():
    with patch.dict(os.environ, {"MCP_MODE": "bad_mode"}):
        client = MCPClient()
    with pytest.raises(ValueError, match="Unsupported MCP mode"):
        await client.call_tool("block_ip", {})


# ── Business methods with audit ──

@pytest.mark.asyncio
async def test_block_ip_business_method():
    with patch.dict(os.environ, {"MCP_MODE": "mock"}):
        client = MCPClient()
    with patch("services.mcp_client.SessionLocal") as mock_sl:
        mock_db = MagicMock()
        mock_sl.return_value = mock_db
        with patch("services.mcp_client.AuditService") as mock_audit:
            result = await client.block_ip("10.0.0.1", device_id=1, operator="admin")
    assert result["success"] is True
    mock_audit.log.assert_called_once()
    call_kwargs = mock_audit.log.call_args.kwargs
    assert call_kwargs["action"] == "mcp_block_ip"
    assert call_kwargs["result"] == "success"
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_unblock_ip_business_method():
    with patch.dict(os.environ, {"MCP_MODE": "mock"}):
        client = MCPClient()
    with patch("services.mcp_client.SessionLocal") as mock_sl:
        mock_db = MagicMock()
        mock_sl.return_value = mock_db
        with patch("services.mcp_client.AuditService") as mock_audit:
            result = await client.unblock_ip("10.0.0.1", operator="admin")
    assert result["success"] is True
    mock_audit.log.assert_called_once()
    call_kwargs = mock_audit.log.call_args.kwargs
    assert call_kwargs["action"] == "mcp_unblock_ip"


@pytest.mark.asyncio
async def test_get_device_status_business():
    with patch.dict(os.environ, {"MCP_MODE": "mock"}):
        client = MCPClient()
    result = await client.get_device_status(1)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_get_acl_rules_business():
    with patch.dict(os.environ, {"MCP_MODE": "mock"}):
        client = MCPClient()
    result = await client.get_acl_rules(1)
    assert result["success"] is True


# ── Close ──

@pytest.mark.asyncio
async def test_close():
    with patch.dict(os.environ, {"MCP_MODE": "mock"}):
        client = MCPClient()
    client.http_client = AsyncMock()
    await client.close()
    client.http_client.aclose.assert_called_once()
