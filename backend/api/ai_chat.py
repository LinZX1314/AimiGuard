from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query as QueryParam, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.auth import require_permissions
from core.database import (
    AIChatMessage,
    AIChatSession,
    AIDecisionLog,
    ScanFinding,
    ScanTask,
    ThreatEvent,
    User,
    get_db,
)
from core.response import APIResponse
from services.ai_engine import ai_engine
from services.prompt_guard import sanitize_input

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

    # S1-01: Prompt 注入检测
    is_safe, _reason = sanitize_input(req.message)
    if not is_safe:
        from services.audit_service import AuditService
        AuditService.log(
            db=db,
            actor=str(current_user.username),
            action="prompt_injection_blocked",
            target="ai_chat",
            target_type="ai_input",
            reason=_reason,
            result="blocked",
            trace_id=trace_id,
        )
        raise HTTPException(status_code=400, detail="输入内容不符合安全规范")

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

    prior_messages = (
        db.query(AIChatMessage)
        .filter(AIChatMessage.session_id == session.id)
        .order_by(AIChatMessage.created_at.asc())
        .limit(20)
        .all()
    )
    history = [{"role": m.role, "content": m.content} for m in prior_messages]

    context_summary = _build_context_summary(db, req, session)
    _t0 = time.monotonic()
    ai_result = await ai_engine.chat(
        req.message,
        context={
            "summary": context_summary,
            "context_type": req.context_type or session.context_type,
            "context_id": req.context_id or session.context_id,
        },
        history=history,
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

    prompt_text = req.message + (context_summary or "")
    decision_log = AIDecisionLog(
        context_type="chat",
        model_name=str(ai_result.get("model") or "unknown"),
        decision=ai_result.get("fallback_reason") or "ok",
        confidence=None,
        reason=response_content[:500] if response_content else None,
        prompt_tokens=None,
        completion_tokens=None,
        prompt_hash=hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:16],
        inference_ms=round(elapsed_ms, 2),
        model_params=json.dumps({"provider": ai_result.get("provider"), "degraded": ai_result.get("degraded")}, ensure_ascii=False),
        trace_id=trace_id,
    )
    db.add(decision_log)
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


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_ai_sessions")),
):
    session = db.query(AIChatSession).filter(AIChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    verify_session_ownership(session, current_user)

    db.query(AIChatMessage).filter(AIChatMessage.session_id == session_id).delete()
    db.delete(session)
    db.commit()

    return APIResponse.success(None, message="会话已删除")


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


@router.get("/decisions")
async def list_decisions(
    context_type: Optional[str] = QueryParam(None, description="筛选 context_type: threat/scan/chat/report"),
    model_name: Optional[str] = QueryParam(None, description="筛选模型名称"),
    min_confidence: Optional[float] = QueryParam(None, description="最低置信度"),
    max_confidence: Optional[float] = QueryParam(None, description="最高置信度"),
    range: str = QueryParam("7d", pattern="^(24h|7d|30d|all)$"),
    page: int = QueryParam(1, ge=1),
    page_size: int = QueryParam(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_ai_sessions")),
):
    """AI 决策日志多维查询（S4-01）"""
    query = db.query(AIDecisionLog)

    if context_type:
        query = query.filter(AIDecisionLog.context_type == context_type)
    if model_name:
        query = query.filter(AIDecisionLog.model_name == model_name)
    if min_confidence is not None:
        query = query.filter(AIDecisionLog.confidence >= min_confidence)
    if max_confidence is not None:
        query = query.filter(AIDecisionLog.confidence <= max_confidence)

    if range != "all":
        delta_map = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
        since = datetime.now(timezone.utc) - delta_map[range]
        query = query.filter(AIDecisionLog.created_at >= since)

    total = query.count()
    rows = (
        query.order_by(AIDecisionLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        {
            "id": r.id,
            "context_type": r.context_type,
            "model_name": r.model_name,
            "decision": r.decision,
            "confidence": r.confidence,
            "reason": r.reason,
            "prompt_hash": r.prompt_hash,
            "inference_ms": r.inference_ms,
            "model_params": r.model_params,
            "prompt_tokens": r.prompt_tokens,
            "completion_tokens": r.completion_tokens,
            "event_id": r.event_id,
            "scan_task_id": r.scan_task_id,
            "trace_id": r.trace_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]

    return APIResponse.success({"total": total, "page": page, "items": items})


@router.get("/monitor/check")
async def ai_monitor_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_ai_sessions")),
):
    """S4-03: 执行 AI 异常行为检测"""
    from services.ai_monitor import run_all_checks

    alerts = run_all_checks(db)
    return APIResponse.success({
        "alerts": alerts,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "alert_count": len(alerts),
    })

