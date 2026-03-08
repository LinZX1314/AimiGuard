"""D2-03 Honeytoken 生命周期管理 API"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import require_permissions
from core.database import Honeytoken, ThreatEvent, User, get_db
from core.response import APIResponse
from services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/honeytokens", tags=["honeytokens"])

VALID_TOKEN_TYPES = {"credential", "api_key", "document", "url"}


class GenerateTokenRequest(BaseModel):
    token_type: str = Field(..., pattern="^(credential|api_key|document|url)$")
    deployed_location: Optional[str] = None


class TriggerTokenRequest(BaseModel):
    value: str = Field(..., min_length=1, description="蜜标原始值")
    attacker_ip: Optional[str] = None


def _token_to_dict(t: Honeytoken) -> dict:
    return {
        "id": t.id,
        "token_type": t.token_type,
        "value_hash": t.value_hash,
        "deployed_location": t.deployed_location,
        "status": t.status,
        "triggered_at": t.triggered_at.isoformat() if t.triggered_at else None,
        "attacker_ip": t.attacker_ip,
        "trigger_count": t.trigger_count,
        "trace_id": t.trace_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _generate_token_value(token_type: str) -> str:
    """生成蜜标原始值"""
    if token_type == "credential":
        user = secrets.token_hex(4)
        pwd = secrets.token_urlsafe(12)
        return f"{user}:{pwd}"
    elif token_type == "api_key":
        return f"sk-honey-{secrets.token_hex(16)}"
    elif token_type == "document":
        return f"doc-tracker-{secrets.token_hex(8)}.pdf"
    elif token_type == "url":
        return f"https://trap.internal/{secrets.token_hex(8)}"
    return secrets.token_hex(16)


@router.get("")
async def list_honeytokens(
    status: Optional[str] = Query(None),
    token_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_events")),
):
    """查询蜜标列表"""
    query = db.query(Honeytoken)
    if status:
        query = query.filter(Honeytoken.status == status)
    if token_type:
        query = query.filter(Honeytoken.token_type == token_type)

    total = query.count()
    rows = (
        query.order_by(Honeytoken.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return APIResponse.success({
        "total": total,
        "page": page,
        "items": [_token_to_dict(t) for t in rows],
    })


@router.post("/generate")
async def generate_honeytoken(
    req: GenerateTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("approve_event")),
):
    """生成蜜标（假凭据/假API Key/假文档/假URL）"""
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))

    raw_value = _generate_token_value(req.token_type)
    value_hash = hashlib.sha256(raw_value.encode()).hexdigest()

    token = Honeytoken(
        token_type=req.token_type,
        value_hash=value_hash,
        deployed_location=req.deployed_location,
        status="ACTIVE",
        trace_id=trace_id,
    )
    db.add(token)
    db.commit()
    db.refresh(token)

    AuditService.log(
        db=db,
        actor=str(current_user.username),
        action="generate_honeytoken",
        target=str(token.id),
        target_type="honeytoken",
        result="success",
        trace_id=trace_id,
    )

    result = _token_to_dict(token)
    result["raw_value"] = raw_value
    return APIResponse.success(result, message="蜜标已生成")


@router.post("/trigger")
async def trigger_honeytoken(
    req: TriggerTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """蜜标触发回调 — 蜜标被使用时调用此接口"""
    value_hash = hashlib.sha256(req.value.encode()).hexdigest()
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))

    token = db.query(Honeytoken).filter(
        Honeytoken.value_hash == value_hash,
        Honeytoken.status == "ACTIVE",
    ).first()

    if not token:
        raise HTTPException(status_code=404, detail="蜜标不存在或已失效")

    now = datetime.now(timezone.utc)
    token.status = "TRIGGERED"
    token.triggered_at = now
    token.attacker_ip = req.attacker_ip
    token.trigger_count = (token.trigger_count or 0) + 1
    token.updated_at = now
    db.commit()

    event = ThreatEvent(
        ip=req.attacker_ip or "unknown",
        source="honeytoken",
        threat_label=f"honeytoken_triggered:{token.token_type}",
        extra_json=f'{{"honeytoken_id": {token.id}, "token_type": "{token.token_type}"}}',
        status="PENDING",
        ai_score=95,
        action_suggest="BLOCK",
        trace_id=trace_id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return APIResponse.success({
        "honeytoken_id": token.id,
        "threat_event_id": event.id,
        "status": "TRIGGERED",
        "ai_score": 95,
    }, message="蜜标已触发，高置信度告警已创建")
