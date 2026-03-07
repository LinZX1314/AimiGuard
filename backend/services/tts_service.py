"""TTS execution service with sandbox mode and provider fallback."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import os
import uuid

import httpx


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TTSService:
    @staticmethod
    def sandbox_mode() -> bool:
        return _bool_env("TTS_SANDBOX_MODE", True)

    @staticmethod
    def _output_dir() -> Path:
        repo_root = Path(__file__).resolve().parents[2]
        output = repo_root / "backend" / "generated_audio"
        output.mkdir(parents=True, exist_ok=True)
        return output

    @staticmethod
    def _build_audio_filename(task_id: Optional[int], trace_id: str, ext: str = "mp3") -> str:
        ts = _utc_now().strftime("%Y%m%d_%H%M%S")
        suffix = f"task{task_id}" if task_id is not None else trace_id[:8]
        return f"tts_{suffix}_{ts}_{uuid.uuid4().hex[:6]}.{ext}"

    @staticmethod
    def _write_audio_bytes(content: bytes, filename: str) -> str:
        output = TTSService._output_dir() / filename
        output.write_bytes(content)
        return f"/generated_audio/{filename}"

    @staticmethod
    async def _call_remote_tts(
        *,
        text: str,
        voice_model: str,
        trace_id: str,
        task_id: Optional[int],
    ) -> Dict[str, Any]:
        provider = os.getenv("TTS_PROVIDER", "local").strip() or "local"
        endpoint = (
            os.getenv("TTS_ENDPOINT", "").strip()
            or os.getenv("TTS_BASE_URL", "").strip()
        )
        if not endpoint:
            return {
                "success": False,
                "simulated": False,
                "provider": provider,
                "audio_path": None,
                "detail": "tts_endpoint_not_configured",
            }

        timeout_seconds = float(os.getenv("TTS_TIMEOUT_SECONDS", "30"))
        model_name = os.getenv("TTS_MODEL", "local-tts-v1").strip() or "local-tts-v1"
        api_key = os.getenv("TTS_API_KEY", "").strip()

        endpoint_url = endpoint.rstrip("/")
        if not endpoint_url.endswith("/synthesize"):
            endpoint_url = f"{endpoint_url}/synthesize"

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "text": text,
            "voice_model": voice_model,
            "model_name": model_name,
            "trace_id": trace_id,
            "task_id": task_id,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(endpoint_url, json=payload, headers=headers)
            if response.status_code >= 400:
                return {
                    "success": False,
                    "simulated": False,
                    "provider": provider,
                    "audio_path": None,
                    "detail": f"tts_http_status_{response.status_code}",
                }

            content_type = (response.headers.get("content-type") or "").lower()
            if "application/json" in content_type:
                body = response.json()
                if isinstance(body, dict):
                    audio_path = body.get("audio_path")
                    if isinstance(audio_path, str) and audio_path.strip():
                        return {
                            "success": True,
                            "simulated": False,
                            "provider": provider,
                            "audio_path": audio_path.strip(),
                            "detail": "remote_audio_path",
                        }

                    b64 = body.get("audio_base64")
                    if isinstance(b64, str) and b64.strip():
                        filename = TTSService._build_audio_filename(task_id, trace_id, ext="mp3")
                        audio_bytes = base64.b64decode(b64)
                        local_path = TTSService._write_audio_bytes(audio_bytes, filename)
                        return {
                            "success": True,
                            "simulated": False,
                            "provider": provider,
                            "audio_path": local_path,
                            "detail": "remote_audio_base64",
                        }

                return {
                    "success": False,
                    "simulated": False,
                    "provider": provider,
                    "audio_path": None,
                    "detail": "tts_json_missing_audio",
                }

            # Audio binary response
            if response.content:
                filename = TTSService._build_audio_filename(task_id, trace_id, ext="mp3")
                local_path = TTSService._write_audio_bytes(response.content, filename)
                return {
                    "success": True,
                    "simulated": False,
                    "provider": provider,
                    "audio_path": local_path,
                    "detail": "remote_audio_binary",
                }

            return {
                "success": False,
                "simulated": False,
                "provider": provider,
                "audio_path": None,
                "detail": "tts_empty_response",
            }
        except Exception as exc:
            return {
                "success": False,
                "simulated": False,
                "provider": provider,
                "audio_path": None,
                "detail": f"tts_request_error:{exc.__class__.__name__}",
            }

    @staticmethod
    async def synthesize(
        *,
        text: str,
        voice_model: str,
        trace_id: str,
        task_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if TTSService.sandbox_mode():
            filename = TTSService._build_audio_filename(task_id, trace_id, ext="mp3")
            # Keep a tiny marker file so output is traceable even in sandbox.
            marker_content = (
                f"sandbox_tts\ntrace_id={trace_id}\nvoice_model={voice_model}\n"
                f"text_preview={text[:120]}"
            ).encode("utf-8")
            local_path = TTSService._write_audio_bytes(marker_content, filename)
            return {
                "success": True,
                "simulated": True,
                "provider": "sandbox",
                "audio_path": local_path,
                "detail": "sandbox_mode",
            }

        return await TTSService._call_remote_tts(
            text=text,
            voice_model=voice_model,
            trace_id=trace_id,
            task_id=task_id,
        )

