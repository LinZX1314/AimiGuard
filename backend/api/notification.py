"""Notification API for in-app notifications."""

from __future__ import annotations

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session

from api.auth import require_permissions, get_current_user
from core.database import User, get_db
from core.response import APIResponse
from services.notification_service import NotificationService

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = NotificationService.list_for_user(
        db, current_user.id, limit=limit, offset=offset, unread_only=unread_only,
    )
    return APIResponse.success(data)


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = NotificationService.mark_read(db, notification_id, current_user.id)
    if not ok:
        raise HTTPException(404, "通知不存在")
    return APIResponse.success(None, message="已标记已读")


@router.post("/read-all")
async def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = NotificationService.mark_all_read(db, current_user.id)
    return APIResponse.success({"marked": count}, message=f"已标记 {count} 条为已读")
