"""STTService tests — sandbox streaming, remote transcription, error handling."""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from services.stt_service import STTService, _bool_env


# ── Sandbox mode ──

def test_sandbox_mode_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("STT_SANDBOX_MODE", None)
        assert STTService.sandbox_mode() is True


def test_sandbox_mode_off():
    with patch.dict(os.environ, {"STT_SANDBOX_MODE": "0"}):
        assert STTService.sandbox_mode() is False


# ── Sandbox streaming ──

@pytest.mark.asyncio
async def test_sandbox_stream_yields_partials():
    gen = STTService.transcribe_stream_sandbox(language="zh")
    event = await gen.__anext__()
    assert event["type"] == "partial"
    assert "你好" in event["text"]

    event2 = await gen.asend(b"fake_audio")
    assert event2["type"] == "partial"
    assert len(event2["text"]) >= len(event["text"])


@pytest.mark.asyncio
async def test_sandbox_stream_reaches_final():
    gen = STTService.transcribe_stream_sandbox()
    await gen.__anext__()
    final_event = None
    for _ in range(10):
        ev = await gen.asend(b"chunk")
        if ev.get("is_final"):
            final_event = ev
            break
    assert final_event is not None
    assert final_event["is_final"] is True
    assert "安全告警" in final_event["text"]


# ── Remote — no endpoint ──

@pytest.mark.asyncio
async def test_remote_no_endpoint():
    with patch.dict(os.environ, {"STT_SANDBOX_MODE": "0", "STT_ENDPOINT": "", "STT_BASE_URL": ""}):
        result = await STTService.transcribe_chunk_remote(b"audio")
    assert result["type"] == "error"
    assert result["detail"] == "stt_endpoint_not_configured"


# ── Remote — HTTP error ──

@pytest.mark.asyncio
async def test_remote_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 503

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch.dict(os.environ, {"STT_ENDPOINT": "http://stt.local"}):
        with patch("services.stt_service.httpx.AsyncClient", return_value=mock_client):
            result = await STTService.transcribe_chunk_remote(b"audio")
    assert result["type"] == "error"
    assert "503" in result["detail"]


# ── Remote — success ──

@pytest.mark.asyncio
async def test_remote_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"type": "partial", "text": "你好世界", "is_final": False}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch.dict(os.environ, {"STT_ENDPOINT": "http://stt.local"}):
        with patch("services.stt_service.httpx.AsyncClient", return_value=mock_client):
            result = await STTService.transcribe_chunk_remote(b"audio", language="zh")
    assert result["type"] == "partial"
    assert result["text"] == "你好世界"


# ── Remote — network error ──

@pytest.mark.asyncio
async def test_remote_network_error():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=ConnectionError("refused"))

    with patch.dict(os.environ, {"STT_ENDPOINT": "http://stt.local"}):
        with patch("services.stt_service.httpx.AsyncClient", return_value=mock_client):
            result = await STTService.transcribe_chunk_remote(b"audio")
    assert result["type"] == "error"
    assert "ConnectionError" in result["detail"]


# ── Remote — with API key and session ──

@pytest.mark.asyncio
async def test_remote_sends_headers():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"type": "final", "text": "done", "is_final": True}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch.dict(os.environ, {"STT_ENDPOINT": "http://stt.local", "STT_API_KEY": "key123"}):
        with patch("services.stt_service.httpx.AsyncClient", return_value=mock_client):
            result = await STTService.transcribe_chunk_remote(
                b"audio", is_final=True, session_id="sess1",
            )
    assert result["is_final"] is True
    call_kwargs = mock_client.post.call_args
    headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
    assert headers.get("Authorization") == "Bearer key123"
    assert headers.get("X-Session-Id") == "sess1"


# ── Endpoint URL normalization ──

@pytest.mark.asyncio
async def test_endpoint_appends_transcribe():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"type": "partial", "text": "ok"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch.dict(os.environ, {"STT_ENDPOINT": "http://stt.local/v1/"}):
        with patch("services.stt_service.httpx.AsyncClient", return_value=mock_client):
            await STTService.transcribe_chunk_remote(b"audio")
    url_called = mock_client.post.call_args[0][0]
    assert url_called.endswith("/transcribe")
