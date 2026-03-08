"""A2-01 漏洞修复工单 CRUD API"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import require_permissions
from core.database import FixTicket, ScanFinding, ScanTask, User, get_db
from core.response import APIResponse
from services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/fix-tickets", tags=["fix-tickets"])

VALID_STATUSES = {"OPEN", "IN_PROGRESS", "RESOLVED", "VERIFIED", "CLOSED", "WONT_FIX"}
VALID_PRIORITIES = {"critical", "high", "medium", "low"}
STATUS_TRANSITIONS = {
    "OPEN": {"IN_PROGRESS", "WONT_FIX"},
    "IN_PROGRESS": {"RESOLVED", "OPEN", "WONT_FIX"},
    "RESOLVED": {"VERIFIED", "IN_PROGRESS"},
    "VERIFIED": {"CLOSED", "IN_PROGRESS"},
    "CLOSED": set(),
    "WONT_FIX": {"OPEN"},
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CreateTicketRequest(BaseModel):
    finding_id: Optional[int] = None
    priority: str = Field("medium", pattern="^(critical|high|medium|low)$")
    assignee: Optional[str] = None
    due_date: Optional[str] = None


class UpdateTicketRequest(BaseModel):
    status: Optional[str] = None
    assignee: Optional[str] = None
    priority: Optional[str] = None
    resolution_note: Optional[str] = None
    due_date: Optional[str] = None


def _ticket_to_dict(t: FixTicket) -> dict:
    return {
        "id": t.id,
        "finding_id": t.finding_id,
        "priority": t.priority,
        "assignee": t.assignee,
        "status": t.status,
        "due_date": t.due_date,
        "resolution_note": t.resolution_note,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        "trace_id": t.trace_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.get("")
async def list_tickets(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_events")),
):
    """查询修复工单列表"""
    query = db.query(FixTicket)
    if status:
        query = query.filter(FixTicket.status == status)
    if priority:
        query = query.filter(FixTicket.priority == priority)

    total = query.count()
    rows = (
        query.order_by(FixTicket.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return APIResponse.success({
        "total": total,
        "page": page,
        "items": [_ticket_to_dict(r) for r in rows],
    })


@router.post("")
async def create_ticket(
    req: CreateTicketRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("approve_event")),
):
    """创建修复工单"""
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))

    if req.finding_id:
        finding = db.query(ScanFinding).filter(ScanFinding.id == req.finding_id).first()
        if not finding:
            raise HTTPException(status_code=404, detail="scan_finding not found")

    ticket = FixTicket(
        finding_id=req.finding_id,
        priority=req.priority,
        assignee=req.assignee,
        status="OPEN",
        due_date=req.due_date,
        trace_id=trace_id,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    AuditService.log(
        db=db,
        actor=str(current_user.username),
        action="create_fix_ticket",
        target=str(ticket.id),
        target_type="fix_ticket",
        result="success",
        trace_id=trace_id,
    )

    return APIResponse.success(_ticket_to_dict(ticket), message="工单已创建")


@router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_events")),
):
    """获取工单详情"""
    ticket = db.query(FixTicket).filter(FixTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    return APIResponse.success(_ticket_to_dict(ticket))


@router.put("/{ticket_id}")
async def update_ticket(
    ticket_id: int,
    req: UpdateTicketRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("approve_event")),
):
    """更新工单（状态流转/指派/备注）"""
    ticket = db.query(FixTicket).filter(FixTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")

    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    updates: dict = {}

    if req.status and req.status != ticket.status:
        allowed = STATUS_TRANSITIONS.get(ticket.status, set())
        if req.status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"状态不允许从 {ticket.status} 转为 {req.status}",
            )
        updates["status"] = req.status
        if req.status in ("CLOSED", "WONT_FIX"):
            updates["closed_at"] = _utc_now()

    if req.assignee is not None:
        updates["assignee"] = req.assignee or None
    if req.priority and req.priority in VALID_PRIORITIES:
        updates["priority"] = req.priority
    if req.resolution_note is not None:
        updates["resolution_note"] = req.resolution_note or None
    if req.due_date is not None:
        updates["due_date"] = req.due_date or None

    if updates:
        updates["updated_at"] = _utc_now()
        db.query(FixTicket).filter(FixTicket.id == ticket_id).update(updates)
        db.commit()

    AuditService.log(
        db=db,
        actor=str(current_user.username),
        action="update_fix_ticket",
        target=str(ticket_id),
        target_type="fix_ticket",
        reason=str(updates) if updates else "no_change",
        result="success",
        trace_id=trace_id,
    )

    ticket = db.query(FixTicket).filter(FixTicket.id == ticket_id).first()
    return APIResponse.success(_ticket_to_dict(ticket), message="工单已更新")


@router.post("/{ticket_id}/retest")
async def trigger_retest(
    ticket_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("approve_event")),
):
    """A2-02: 复测触发 — 工单状态为 RESOLVED 时可一键触发复测扫描"""
    ticket = db.query(FixTicket).filter(FixTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")

    if ticket.status != "RESOLVED":
        raise HTTPException(
            status_code=400,
            detail=f"仅 RESOLVED 状态的工单可触发复测，当前状态: {ticket.status}",
        )

    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))

    finding = None
    asset_id = None
    target = "unknown"
    if ticket.finding_id:
        finding = db.query(ScanFinding).filter(ScanFinding.id == ticket.finding_id).first()
        if finding:
            task = db.query(ScanTask).filter(ScanTask.id == finding.task_id).first()
            if task:
                asset_id = task.asset_id
                target = task.target

    retest_task = ScanTask(
        asset_id=asset_id or 0,
        target=target,
        target_type="retest",
        tool_name="nmap",
        state="QUEUED",
        trace_id=trace_id,
    )
    db.add(retest_task)
    db.commit()
    db.refresh(retest_task)

    AuditService.log(
        db=db,
        actor=str(current_user.username),
        action="trigger_retest",
        target=str(ticket_id),
        target_type="fix_ticket",
        reason=f"retest_scan_task_id={retest_task.id}",
        result="success",
        trace_id=trace_id,
    )

    return APIResponse.success(
        {
            "ticket_id": ticket_id,
            "scan_task_id": retest_task.id,
            "target": target,
            "state": "QUEUED",
        },
        message="复测扫描已创建",
    )
