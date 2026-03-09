"""Streaming Speech-to-Text WebSocket API."""

from __future__ import annotations

import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query

from services.stt_service import STTService

router = APIRouter(prefix="/api/v1/stt", tags=["stt"])


def _get_token_from_query(token: str = Query(default="")) -> str:
    """Extract token from WebSocket query string."""
    return token


@router.websocket("/stream")
async def stt_stream(
    websocket: WebSocket,
    token: str = Depends(_get_token_from_query),
):
    """WebSocket endpoint for streaming speech-to-text.

    Client sends binary audio frames (PCM/webm).
    Server responds with JSON messages:
        {"type": "partial", "text": "...", "is_final": false}
        {"type": "final",   "text": "...", "is_final": true}
        {"type": "error",   "text": "",    "detail": "..."}
        {"type": "ready",   "session_id": "..."}

    Query params:
        token  – JWT access token for authentication
        lang   – language hint (default: zh)
    """
    await websocket.accept()

    session_id = uuid.uuid4().hex[:12]

    # Send ready event
    await websocket.send_json({
        "type": "ready",
        "session_id": session_id,
    })

    if STTService.sandbox_mode():
        await _handle_sandbox(websocket, session_id)
    else:
        await _handle_remote(websocket, session_id)


async def _handle_sandbox(websocket: WebSocket, session_id: str):
    """Handle sandbox (simulated) STT streaming."""
    gen = STTService.transcribe_stream_sandbox()
    # Prime the generator
    await gen.__anext__()

    try:
        while True:
            data = await websocket.receive()

            if data.get("type") == "websocket.disconnect":
                break

            # Accept both binary audio frames and text commands
            if "bytes" in data and data["bytes"]:
                event = await gen.asend(data["bytes"])
                await websocket.send_json(event)
            elif "text" in data:
                text = data["text"]
                if text == "stop":
                    # Send final result
                    event = await gen.asend(b"")
                    event["type"] = "final"
                    event["is_final"] = True
                    await websocket.send_json(event)
                    break
    except WebSocketDisconnect:
        pass
    finally:
        await gen.aclose()


async def _handle_remote(websocket: WebSocket, session_id: str):
    """Handle remote STT provider streaming."""
    try:
        while True:
            data = await websocket.receive()

            if data.get("type") == "websocket.disconnect":
                break

            is_stop = False
            audio_bytes = b""

            if "bytes" in data and data["bytes"]:
                audio_bytes = data["bytes"]
            elif "text" in data:
                if data["text"] == "stop":
                    is_stop = True

            result = await STTService.transcribe_chunk_remote(
                audio_data=audio_bytes,
                is_final=is_stop,
                session_id=session_id,
            )

            if is_stop:
                result["type"] = "final"
                result["is_final"] = True

            await websocket.send_json(result)

            if is_stop:
                break
    except WebSocketDisconnect:
        pass
