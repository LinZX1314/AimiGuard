from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.auth import require_permissions
from core.database import (
    AIChatMessage,
    AIChatSession,
    ScanFinding,
    ScanTask,
    ThreatEvent,
    User,
    get_db,
)
from core.response import APIResponse
from services.ai_engine import ai_engine

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[int] = None
    context_type: Optional[str] = None
    context_id: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str
    created_at: datetime


def _safe_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def verify_session_ownership(session: AIChatSession, user: User) -> None:
    if session.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    if session.expires_at:
        expires_at_utc = (
            session.expires_at.replace(tzinfo=timezone.utc)
            if session.expires_at.tzinfo is None
            else session.expires_at
        )
        if expires_at_utc < datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="会话已过期")


def _build_context_summary(db: Session, req: ChatRequest, session: AIChatSession) -> str:
    parts: List[str] = []
    ctx_type = req.context_type or session.context_type
    ctx_id = req.context_id or (str(session.context_id) if session.context_id else None)
    parsed_ctx_id = _safe_int(ctx_id)

    if ctx_type == "event" and parsed_ctx_id is not None:
        ev = db.query(ThreatEvent).filter(ThreatEvent.id == parsed_ctx_id).first()
        if ev:
            parts.append(
                f"[事件#{ev.id}] IP={ev.ip} 来源={ev.source} 标签={ev.threat_label} "
                f"AI评分={ev.ai_score} 状态={ev.status}"
            )
    elif ctx_type == "scan_task" and parsed_ctx_id is not None:
        task = db.query(ScanTask).filter(ScanTask.id == parsed_ctx_id).first()
        if task:
            parts.append(
                f"[扫描#{task.id}] 目标={task.target} 工具={task.tool_name} 状态={task.state} "
                f"Profile={task.profile}"
            )
            findings_count = (
                db.query(func.count(ScanFinding.id))
                .filter(ScanFinding.scan_task_id == task.id)
                .scalar()
                or 0
            )
            high_count = (
                db.query(func.count(ScanFinding.id))
                .filter(ScanFinding.scan_task_id == task.id, ScanFinding.severity == "HIGH")
                .scalar()
                or 0
            )
            parts.append(f"发现 {findings_count} 个漏洞（高危 {high_count}）")

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_alerts = (
        db.query(func.count(ThreatEvent.id))
        .filter(ThreatEvent.created_at >= today)
        .scalar()
        or 0
    )
    pending_events = (
        db.query(func.count(ThreatEvent.id))
        .filter(ThreatEvent.status == "PENDING")
        .scalar()
        or 0
    )
    parts.append(f"系统概况: 今日告警 {today_alerts} / 待处理 {pending_events}")
    return " | ".join(parts)


@router.post("/chat")
async def chat(
    req: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("ai_chat")),
):
    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    session: Optional[AIChatSession] = None

    if req.session_id:
        session = db.query(AIChatSession).filter(AIChatSession.id == req.session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        verify_session_ownership(session, current_user)
    else:
        session = AIChatSession(
            user_id=current_user.id,
            operator=current_user.username,
            context_type=req.context_type,
            context_id=_safe_int(req.context_id),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.add(session)
        db.flush()

    user_msg = AIChatMessage(
        session_id=session.id,
        role="user",
        content=req.message,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg)

    context_summary = _build_context_summary(db, req, session)
    _t0 = time.monotonic()
    ai_result = await ai_engine.chat(
        req.message,
        context={
            "summary": context_summary,
            "context_type": req.context_type or session.context_type,
            "context_id": req.context_id or session.context_id,
        },
        trace_id=trace_id,
        with_meta=True,
    )
    elapsed_ms = (time.monotonic() - _t0) * 1000

    response_content = str(ai_result.get("text") or "").strip()
    if not response_content:
        response_content = "模型返回为空，请稍后重试。"

    try:
        from services.metrics_service import metrics

        metrics.inc("ai_chat_requests")
        metrics.record_latency("ai_chat", elapsed_ms)
    except Exception:
        pass

    ai_msg = AIChatMessage(
        session_id=session.id,
        role="assistant",
        content=response_content,
        created_at=datetime.now(timezone.utc),
    )
    db.add(ai_msg)
    db.commit()

    return APIResponse.success(
        {
            "session_id": session.id,
            "message": response_content,
            "context": {
                "type": req.context_type or session.context_type,
                "id": req.context_id or session.context_id,
                "summary": context_summary,
            },
            "meta": {
                "degraded": bool(ai_result.get("degraded")),
                "fallback_reason": ai_result.get("fallback_reason"),
                "provider": ai_result.get("provider"),
                "model": ai_result.get("model"),
                "elapsed_ms": round(elapsed_ms, 2),
                "trace_id": trace_id,
            },
        },
        trace_id=trace_id,
    )


@router.get("/sessions")
async def get_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_ai_sessions")),
):
    sessions = (
        db.query(AIChatSession)
        .filter(AIChatSession.user_id == current_user.id)
        .order_by(AIChatSession.started_at.desc())
        .limit(50)
        .all()
    )
    return APIResponse.success(
        [
            {
                "id": s.id,
                "user_id": s.user_id,
                "context_type": s.context_type,
                "context_id": s.context_id,
                "operator": s.operator,
                "started_at": s.started_at,
                "expires_at": s.expires_at,
            }
            for s in sessions
        ]
    )


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessage])
async def get_session_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_ai_sessions")),
):
    session = db.query(AIChatSession).filter(AIChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    verify_session_ownership(session, current_user)
    messages = (
        db.query(AIChatMessage)
        .filter(AIChatMessage.session_id == session_id)
        .order_by(AIChatMessage.created_at.asc())
        .all()
    )
    return messages


@router.get("/chat/{session_id}/context")
async def get_session_context(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_ai_sessions")),
):
    session = db.query(AIChatSession).filter(AIChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    verify_session_ownership(session, current_user)
    messages = (
        db.query(AIChatMessage)
        .filter(AIChatMessage.session_id == session_id)
        .order_by(AIChatMessage.created_at.asc())
        .all()
    )

    return APIResponse.success(
        {
            "session_id": session.id,
            "user_id": session.user_id,
            "context_type": session.context_type,
            "context_id": session.context_id,
            "started_at": session.started_at,
            "expires_at": session.expires_at,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at,
                }
                for msg in messages
            ],
        }
    )

