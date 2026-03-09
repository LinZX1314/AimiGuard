"""TTSService tests — sandbox mode, remote call, filename generation."""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import base64
import json

from services.tts_service import TTSService, _bool_env


# ── _bool_env helper ──

def test_bool_env_true_values():
    for val in ("1", "true", "True", "YES", "on", " 1 "):
        with patch.dict(os.environ, {"TEST_FLAG": val}):
            assert _bool_env("TEST_FLAG", False) is True


def test_bool_env_false_values():
    for val in ("0", "false", "no", "off", "random"):
        with patch.dict(os.environ, {"TEST_FLAG": val}):
            assert _bool_env("TEST_FLAG", True) is False


def test_bool_env_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("TEST_FLAG_MISSING", None)
        assert _bool_env("TEST_FLAG_MISSING", True) is True
        assert _bool_env("TEST_FLAG_MISSING", False) is False


# ── Sandbox mode ──

@pytest.mark.asyncio
async def test_synthesize_sandbox():
    with patch.dict(os.environ, {"TTS_SANDBOX_MODE": "1"}):
        result = await TTSService.synthesize(
            text="你好世界", voice_model="zh-CN", trace_id="t1",
        )
    assert result["success"] is True
    assert result["simulated"] is True
    assert result["provider"] == "sandbox"
    assert result["audio_path"] is not None
    assert "generated_audio" in result["audio_path"]


@pytest.mark.asyncio
async def test_synthesize_sandbox_with_task_id():
    with patch.dict(os.environ, {"TTS_SANDBOX_MODE": "1"}):
        result = await TTSService.synthesize(
            text="test", voice_model="en", trace_id="t2", task_id=42,
        )
    assert result["success"] is True
    assert "task42" in result["audio_path"]


# ── Remote call — no endpoint ──

@pytest.mark.asyncio
async def test_remote_no_endpoint():
    with patch.dict(os.environ, {"TTS_SANDBOX_MODE": "0", "TTS_ENDPOINT": "", "TTS_BASE_URL": ""}):
        result = await TTSService.synthesize(
            text="test", voice_model="en", trace_id="t3",
        )
    assert result["success"] is False
    assert result["detail"] == "tts_endpoint_not_configured"


# ── Remote call — HTTP error ──

@pytest.mark.asyncio
async def test_remote_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 500

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch.dict(os.environ, {"TTS_SANDBOX_MODE": "0", "TTS_ENDPOINT": "http://tts.local"}):
        with patch("services.tts_service.httpx.AsyncClient", return_value=mock_client):
            result = await TTSService.synthesize(
                text="test", voice_model="en", trace_id="t4",
            )
    assert result["success"] is False
    assert "500" in result["detail"]


# ── Remote call — JSON with audio_path ──

@pytest.mark.asyncio
async def test_remote_json_audio_path():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"audio_path": "/audio/output.mp3"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch.dict(os.environ, {"TTS_SANDBOX_MODE": "0", "TTS_ENDPOINT": "http://tts.local"}):
        with patch("services.tts_service.httpx.AsyncClient", return_value=mock_client):
            result = await TTSService.synthesize(
                text="test", voice_model="en", trace_id="t5",
            )
    assert result["success"] is True
    assert result["audio_path"] == "/audio/output.mp3"
    assert result["detail"] == "remote_audio_path"


# ── Remote call — JSON with base64 audio ──

@pytest.mark.asyncio
async def test_remote_json_audio_base64():
    audio_b64 = base64.b64encode(b"fake_audio_data").decode()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"audio_base64": audio_b64}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch.dict(os.environ, {"TTS_SANDBOX_MODE": "0", "TTS_ENDPOINT": "http://tts.local"}):
        with patch("services.tts_service.httpx.AsyncClient", return_value=mock_client):
            result = await TTSService.synthesize(
                text="test", voice_model="en", trace_id="t6",
            )
    assert result["success"] is True
    assert result["detail"] == "remote_audio_base64"


# ── Remote call — binary audio response ──

@pytest.mark.asyncio
async def test_remote_binary_audio():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "audio/mpeg"}
    mock_response.content = b"fake_mp3_bytes"

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch.dict(os.environ, {"TTS_SANDBOX_MODE": "0", "TTS_ENDPOINT": "http://tts.local"}):
        with patch("services.tts_service.httpx.AsyncClient", return_value=mock_client):
            result = await TTSService.synthesize(
                text="test", voice_model="en", trace_id="t7",
            )
    assert result["success"] is True
    assert result["detail"] == "remote_audio_binary"


# ── Remote call — network error ──

@pytest.mark.asyncio
async def test_remote_network_error():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=ConnectionError("refused"))

    with patch.dict(os.environ, {"TTS_SANDBOX_MODE": "0", "TTS_ENDPOINT": "http://tts.local"}):
        with patch("services.tts_service.httpx.AsyncClient", return_value=mock_client):
            result = await TTSService.synthesize(
                text="test", voice_model="en", trace_id="t8",
            )
    assert result["success"] is False
    assert "ConnectionError" in result["detail"]


# ── Filename generation ──

def test_build_audio_filename_with_task_id():
    fname = TTSService._build_audio_filename(42, "trace123")
    assert fname.startswith("tts_task42_")
    assert fname.endswith(".mp3")


def test_build_audio_filename_without_task_id():
    fname = TTSService._build_audio_filename(None, "trace123")
    assert "trace123" in fname
