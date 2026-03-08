from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

DEFENSE_EVENTS_CHANNEL = "defense.events"
SCAN_TASKS_CHANNEL = "scan.tasks"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class EventBroadcaster:
    def __init__(self) -> None:
        self._channels: dict[str, dict[str, WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, channel: str, websocket: WebSocket) -> str:
        client_id = uuid.uuid4().hex
        await websocket.accept()
        async with self._lock:
            self._channels.setdefault(channel, {})[client_id] = websocket
        return client_id

    async def disconnect(self, channel: str, client_id: str) -> None:
        async with self._lock:
            channel_clients = self._channels.get(channel)
            if channel_clients is None:
                return
            channel_clients.pop(client_id, None)
            if not channel_clients:
                self._channels.pop(channel, None)

    async def publish(
        self,
        channel: str,
        event_type: str,
        data: dict[str, Any] | None = None,
        *,
        trace_id: str | None = None,
        reason: str | None = None,
    ) -> int:
        payload: dict[str, Any] = {
            "type": event_type,
            "channel": channel,
            "timestamp": _utc_iso(),
            "data": data or {},
        }
        if trace_id:
            payload["trace_id"] = trace_id
        if reason:
            payload["reason"] = reason
        return await self.broadcast(channel, payload)

    async def broadcast(self, channel: str, payload: dict[str, Any]) -> int:
        async with self._lock:
            subscribers = list(self._channels.get(channel, {}).items())

        if not subscribers:
            return 0

        stale_client_ids: list[str] = []
        delivered = 0
        for client_id, websocket in subscribers:
            try:
                await websocket.send_json(payload)
                delivered += 1
            except Exception:
                stale_client_ids.append(client_id)

        if stale_client_ids:
            async with self._lock:
                channel_clients = self._channels.get(channel)
                if channel_clients is not None:
                    for client_id in stale_client_ids:
                        channel_clients.pop(client_id, None)
                    if not channel_clients:
                        self._channels.pop(channel, None)

        return delivered


event_broadcaster = EventBroadcaster()
