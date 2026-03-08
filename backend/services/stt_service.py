"""STT (Speech-to-Text) service with sandbox mode and provider fallback."""

from __future__ import annotations

import os
import asyncio
from typing import Any, AsyncGenerator, Dict, Optional

import httpx


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class STTService:
    """Streaming speech-to-text service.

    In sandbox mode, simulates transcription by returning placeholder text
    with a realistic streaming delay.  When a remote STT endpoint is
    configured, audio chunks are forwarded for real transcription.
    """

    @staticmethod
    def sandbox_mode() -> bool:
        return _bool_env("STT_SANDBOX_MODE", True)

    # ── Sandbox simulation ──────────────────────────────────────────

    @staticmethod
    async def transcribe_stream_sandbox(
        language: str = "zh",
    ) -> AsyncGenerator[Dict[str, Any], bytes | None]:
        """Generator that simulates streaming STT.

        Usage::

            gen = STTService.transcribe_stream_sandbox()
            await gen.__anext__()          # prime
            for chunk in audio_chunks:
                event = await gen.asend(chunk)
                yield event               # partial / final
        """
        sandbox_sentences = [
            "你好",
            "你好，请",
            "你好，请帮我",
            "你好，请帮我分析",
            "你好，请帮我分析一下",
            "你好，请帮我分析一下最近的",
            "你好，请帮我分析一下最近的安全告警",
        ]
        idx = 0
        while True:
            _chunk = yield {
                "type": "partial",
                "text": sandbox_sentences[min(idx, len(sandbox_sentences) - 1)],
                "is_final": idx >= len(sandbox_sentences) - 1,
            }
            if idx < len(sandbox_sentences) - 1:
                idx += 1
            await asyncio.sleep(0.15)

    # ── Remote provider ─────────────────────────────────────────────

    @staticmethod
    async def transcribe_chunk_remote(
        audio_data: bytes,
        *,
        language: str = "zh",
        is_final: bool = False,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a single audio chunk to a remote STT API."""
        provider = os.getenv("STT_PROVIDER", "local").strip() or "local"
        endpoint = (
            os.getenv("STT_ENDPOINT", "").strip()
            or os.getenv("STT_BASE_URL", "").strip()
        )
        if not endpoint:
            return {
                "type": "error",
                "text": "",
                "detail": "stt_endpoint_not_configured",
            }

        timeout_seconds = float(os.getenv("STT_TIMEOUT_SECONDS", "10"))
        api_key = os.getenv("STT_API_KEY", "").strip()

        endpoint_url = endpoint.rstrip("/")
        if not endpoint_url.endswith("/transcribe"):
            endpoint_url = f"{endpoint_url}/transcribe"

        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    endpoint_url,
                    content=audio_data,
                    headers={
                        **headers,
                        "Content-Type": "application/octet-stream",
                        "X-Language": language,
                        "X-Is-Final": str(is_final).lower(),
                        "X-Session-Id": session_id or "",
                    },
                )
            if response.status_code >= 400:
                return {
                    "type": "error",
                    "text": "",
                    "detail": f"stt_http_{response.status_code}",
                }
            body = response.json()
            return {
                "type": body.get("type", "partial"),
                "text": body.get("text", ""),
                "is_final": body.get("is_final", is_final),
            }
        except Exception as exc:
            return {
                "type": "error",
                "text": "",
                "detail": f"stt_request_error:{exc.__class__.__name__}",
            }
