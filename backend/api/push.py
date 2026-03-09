"""Push channel management API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import require_permissions
from core.database import PushChannel, PushLog, SessionLocal, User, get_db
from core.response import APIResponse
from services.audit_service import AuditService
from services.push_service import PushService

router = APIRouter(prefix="/api/v1/push", tags=["push"])

SUPPORTED_TYPES = ["webhook", "wecom", "dingtalk", "feishu", "email"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PushChannelCreate(BaseModel):
    channel_type: str
    channel_name: str
    target: str
    config_json: Optional[str] = None
    enabled: int = 1


class PushChannelUpdate(BaseModel):
    channel_name: Optional[str] = None
    target: Optional[str] = None
    config_json: Optional[str] = None
    enabled: Optional[int] = None


@router.get("/channels")
async def list_channels(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_push")),
):
    channels = db.query(PushChannel).order_by(PushChannel.created_at.desc()).all()
    return APIResponse.success(
        [
            {
                "id": c.id,
                "channel_type": c.channel_type,
                "channel_name": c.channel_name,
                "target": c.target,
                "config_json": c.config_json,
                "enabled": c.enabled,
                "created_at": c.created_at.isoformat().replace("+00:00", "Z") if c.created_at else None,
                "updated_at": c.updated_at.isoformat().replace("+00:00", "Z") if c.updated_at else None,
            }
            for c in channels
        ]
    )


@router.post("/channels")
async def create_channel(
    data: PushChannelCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("manage_push")),
):
    if data.channel_type not in SUPPORTED_TYPES:
        raise HTTPException(400, f"不支持的通道类型，可选: {', '.join(SUPPORTED_TYPES)}")

    existing = db.query(PushChannel).filter(PushChannel.channel_name == data.channel_name).first()
    if existing:
        raise HTTPException(400, "通道名称已存在")

    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    channel = PushChannel(
        channel_type=data.channel_type,
        channel_name=data.channel_name,
        target=data.target,
        config_json=data.config_json,
        enabled=data.enabled,
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    AuditService.log(
        db=db,
        actor=str(current_user.username),
        action="create_push_channel",
        target=data.channel_name,
        target_type="push_channel",
        trace_id=trace_id,
    )

    return APIResponse.success(
        {"id": channel.id, "channel_name": channel.channel_name},
        message="推送通道已创建",
        trace_id=trace_id,
    )


@router.put("/channels/{channel_id}")
async def update_channel(
    channel_id: int,
    data: PushChannelUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("manage_push")),
):
    channel = db.query(PushChannel).filter(PushChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(404, "通道不存在")

    if data.channel_name is not None:
        channel.channel_name = data.channel_name
    if data.target is not None:
        channel.target = data.target
    if data.config_json is not None:
        channel.config_json = data.config_json
    if data.enabled is not None:
        channel.enabled = data.enabled
    channel.updated_at = _utc_now()
    db.commit()

    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    AuditService.log(
        db=db,
        actor=str(current_user.username),
        action="update_push_channel",
        target=str(channel_id),
        target_type="push_channel",
        trace_id=trace_id,
    )
    return APIResponse.success(None, message="更新成功", trace_id=trace_id)


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("manage_push")),
):
    channel = db.query(PushChannel).filter(PushChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(404, "通道不存在")

    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    channel_name = channel.channel_name
    db.delete(channel)
    db.commit()

    AuditService.log(
        db=db,
        actor=str(current_user.username),
        action="delete_push_channel",
        target=channel_name,
        target_type="push_channel",
        trace_id=trace_id,
    )
    return APIResponse.success(None, message="删除成功", trace_id=trace_id)


@router.post("/channels/{channel_id}/test")
async def test_channel(
    channel_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("manage_push")),
):
    channel = db.query(PushChannel).filter(PushChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(404, "通道不存在")

    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    test_message = (
        f"[Aimiguan test] channel={channel.channel_name} "
        f"type={channel.channel_type} trace_id={trace_id}"
    )
    result = await PushService.send_test(channel, test_message, trace_id)

    AuditService.log(
        db=db,
        actor=str(current_user.username),
        action="test_push_channel",
        target=str(channel_id),
        target_type="push_channel",
        reason=result.get("detail"),
        result="success" if result.get("success") else "FAILED",
        error_message=None if result.get("success") else str(result.get("detail")),
        trace_id=trace_id,
    )

    if not result.get("success"):
        raise HTTPException(status_code=502, detail=f"推送测试失败: {result.get('detail')}")

    return APIResponse.success(
        result,
        message="推送测试成功",
        trace_id=trace_id,
    )


@router.get("/logs")
async def list_push_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    channel_id: Optional[int] = Query(None),
    success: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_push")),
):
    q = db.query(PushLog)
    if channel_id is not None:
        q = q.filter(PushLog.channel_id == channel_id)
    if success is not None:
        q = q.filter(PushLog.success == success)
    total = q.count()
    items = q.order_by(PushLog.created_at.desc()).offset(offset).limit(limit).all()
    return APIResponse.success({
        "total": total,
        "items": [
            {
                "id": log.id,
                "channel_id": log.channel_id,
                "channel_type": log.channel_type,
                "channel_name": log.channel_name,
                "target": log.target,
                "message_preview": log.message_preview,
                "success": bool(log.success),
                "status": log.status,
                "detail": log.detail,
                "retry_count": log.retry_count,
                "max_retries": log.max_retries,
                "trace_id": log.trace_id,
                "trigger_source": log.trigger_source,
                "created_at": log.created_at.isoformat().replace("+00:00", "Z") if log.created_at else None,
            }
            for log in items
        ],
    })


@router.post("/logs/{log_id}/retry")
async def retry_push_log(
    log_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("manage_push")),
):
    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    result = await PushService.retry_push_log(SessionLocal, log_id)

    AuditService.log(
        db=db,
        actor=str(current_user.username),
        action="retry_push_log",
        target=str(log_id),
        target_type="push_log",
        result="success" if result.get("success") else "FAILED",
        trace_id=trace_id,
    )

    if not result.get("success"):
        raise HTTPException(502, f"重试失败: {result.get('detail')}")

    return APIResponse.success(result, message="重试成功", trace_id=trace_id)

