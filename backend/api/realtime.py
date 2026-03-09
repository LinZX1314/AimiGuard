from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from api.auth import get_user_permissions, resolve_current_user_from_token
from core.database import SessionLocal, User
from services.event_broadcaster import DEFENSE_EVENTS_CHANNEL, SCAN_TASKS_CHANNEL, event_broadcaster

router = APIRouter(tags=["realtime"])


def _get_token_from_query(token: str = Query(default="")) -> str:
    return token.strip()


def _authorize_websocket(token: str, permission: str, db: Session) -> User:
    user = resolve_current_user_from_token(token, db)
    permissions = set(get_user_permissions(user, db))
    if permission not in permissions:
        raise HTTPException(status_code=403, detail=f"缺少权限: {permission}")
    return user


async def _handle_channel(
    websocket: WebSocket,
    *,
    token: str,
    channel: str,
    required_permission: str,
) -> None:
    db = SessionLocal()
    client_id: str | None = None
    try:
        await websocket.accept()

        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="missing_token")
            return

        user = _authorize_websocket(token, required_permission, db)
        client_id = await event_broadcaster.connect(channel, websocket)
        await websocket.send_json(
            {
                "type": "ready",
                "channel": channel,
                "data": {
                    "username": str(user.username),
                    "required_permission": required_permission,
                },
            }
        )

        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("text") == "ping":
                await websocket.send_json({"type": "pong", "channel": channel, "data": {}})
    except WebSocketDisconnect:
        pass
    except HTTPException as exc:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=str(exc.detail),
        )
    finally:
        if client_id is not None:
            await event_broadcaster.disconnect(channel, client_id)
        db.close()


@router.websocket("/ws/defense/events")
async def defense_events_stream(
    websocket: WebSocket,
    token: str = Query(default=""),
) -> None:
    await _handle_channel(
        websocket,
        token=token.strip(),
        channel=DEFENSE_EVENTS_CHANNEL,
        required_permission="view_events",
    )


@router.websocket("/ws/scan/tasks")
async def scan_tasks_stream(
    websocket: WebSocket,
    token: str = Query(default=""),
) -> None:
    await _handle_channel(
        websocket,
        token=token.strip(),
        channel=SCAN_TASKS_CHANNEL,
        required_permission="scan:view",
    )
