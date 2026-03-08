"""D2-01 蜜罐策略管理 CRUD API"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import require_permissions
from core.database import HoneypotConfig, ThreatEvent, User, get_db
from core.response import APIResponse
from services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/honeypots", tags=["honeypots"])

VALID_TYPES = {"ssh", "http", "ftp", "rdp", "smb", "telnet", "mysql", "redis", "custom"}
VALID_STATUSES = {"ACTIVE", "INACTIVE", "DEPLOYING", "FAILED"}


class CreateHoneypotRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., pattern="^(ssh|http|ftp|rdp|smb|telnet|mysql|redis|custom)$")
    target_service: Optional[str] = None
    bait_data: Optional[str] = None


class UpdateHoneypotRequest(BaseModel):
    name: Optional[str] = None
    target_service: Optional[str] = None
    bait_data: Optional[str] = None
    status: Optional[str] = None


def _hp_to_dict(hp: HoneypotConfig) -> dict:
    return {
        "id": hp.id,
        "name": hp.name,
        "type": hp.type,
        "target_service": hp.target_service,
        "bait_data": hp.bait_data,
        "status": hp.status,
        "hfish_node_id": hp.hfish_node_id,
        "trace_id": hp.trace_id,
        "created_at": hp.created_at.isoformat() if hp.created_at else None,
        "updated_at": hp.updated_at.isoformat() if hp.updated_at else None,
    }


@router.get("")
async def list_honeypots(
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_events")),
):
    """查询蜜罐配置列表"""
    query = db.query(HoneypotConfig)
    if status:
        query = query.filter(HoneypotConfig.status == status)
    if type:
        query = query.filter(HoneypotConfig.type == type)

    total = query.count()
    rows = (
        query.order_by(HoneypotConfig.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return APIResponse.success({
        "total": total,
        "page": page,
        "items": [_hp_to_dict(r) for r in rows],
    })


@router.post("")
async def create_honeypot(
    req: CreateHoneypotRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("approve_event")),
):
    """创建蜜罐配置"""
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))

    hp = HoneypotConfig(
        name=req.name,
        type=req.type,
        target_service=req.target_service,
        bait_data=req.bait_data,
        status="INACTIVE",
        trace_id=trace_id,
    )
    db.add(hp)
    db.commit()
    db.refresh(hp)

    AuditService.log(
        db=db,
        actor=str(current_user.username),
        action="create_honeypot",
        target=str(hp.id),
        target_type="honeypot_config",
        result="success",
        trace_id=trace_id,
    )

    return APIResponse.success(_hp_to_dict(hp), message="蜜罐配置已创建")


@router.get("/{honeypot_id}")
async def get_honeypot(
    honeypot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_events")),
):
    """获取蜜罐详情"""
    hp = db.query(HoneypotConfig).filter(HoneypotConfig.id == honeypot_id).first()
    if not hp:
        raise HTTPException(status_code=404, detail="蜜罐配置不存在")
    return APIResponse.success(_hp_to_dict(hp))


@router.put("/{honeypot_id}")
async def update_honeypot(
    honeypot_id: int,
    req: UpdateHoneypotRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("approve_event")),
):
    """更新蜜罐配置"""
    hp = db.query(HoneypotConfig).filter(HoneypotConfig.id == honeypot_id).first()
    if not hp:
        raise HTTPException(status_code=404, detail="蜜罐配置不存在")

    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    updates: dict = {}

    if req.name is not None:
        updates["name"] = req.name
    if req.target_service is not None:
        updates["target_service"] = req.target_service or None
    if req.bait_data is not None:
        updates["bait_data"] = req.bait_data or None
    if req.status and req.status in VALID_STATUSES:
        updates["status"] = req.status

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc)
        db.query(HoneypotConfig).filter(HoneypotConfig.id == honeypot_id).update(updates)
        db.commit()

    AuditService.log(
        db=db,
        actor=str(current_user.username),
        action="update_honeypot",
        target=str(honeypot_id),
        target_type="honeypot_config",
        reason=str(updates) if updates else "no_change",
        result="success",
        trace_id=trace_id,
    )

    hp = db.query(HoneypotConfig).filter(HoneypotConfig.id == honeypot_id).first()
    return APIResponse.success(_hp_to_dict(hp), message="蜜罐配置已更新")


@router.get("/{honeypot_id}/alerts")
async def get_honeypot_alerts(
    honeypot_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_events")),
):
    """获取蜜罐关联的告警事件"""
    hp = db.query(HoneypotConfig).filter(HoneypotConfig.id == honeypot_id).first()
    if not hp:
        raise HTTPException(status_code=404, detail="蜜罐配置不存在")

    query = db.query(ThreatEvent).filter(ThreatEvent.source == "hfish")
    total = query.count()
    events = (
        query.order_by(ThreatEvent.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return APIResponse.success({
        "total": total,
        "page": page,
        "items": [
            {
                "id": e.id,
                "ip": e.ip,
                "threat_label": e.threat_label,
                "status": e.status,
                "ai_score": e.ai_score,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    })
