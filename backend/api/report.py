from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.auth import require_permissions
from core.database import (
    AIDecisionLog,
    AIReport,
    ExecutionTask,
    ScanFinding,
    ScanTask,
    ThreatEvent,
    User,
    get_db,
)
from core.response import APIResponse
from services.ai_engine import ai_engine
from services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/report", tags=["report"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _build_defense_summary(db: Session, since: datetime) -> str:
    total = db.query(func.count(ThreatEvent.id)).filter(ThreatEvent.created_at >= since).scalar() or 0
    pending = (
        db.query(func.count(ThreatEvent.id))
        .filter(ThreatEvent.created_at >= since, ThreatEvent.status == "PENDING")
        .scalar()
        or 0
    )
    high_risk = (
        db.query(func.count(ThreatEvent.id))
        .filter(ThreatEvent.created_at >= since, ThreatEvent.ai_score >= 80)
        .scalar()
        or 0
    )
    blocked = (
        db.query(func.count(ExecutionTask.id))
        .filter(ExecutionTask.state == "SUCCESS", ExecutionTask.ended_at >= since)
        .scalar()
        or 0
    )
    return f"告警总数 {total} / 待处理 {pending} / 高危 {high_risk} / 成功封禁 {blocked}"


def _build_scan_summary(db: Session, since: datetime) -> str:
    total_tasks = db.query(func.count(ScanTask.id)).filter(ScanTask.created_at >= since).scalar() or 0
    completed = (
        db.query(func.count(ScanTask.id))
        .filter(ScanTask.state == "REPORTED", ScanTask.created_at >= since)
        .scalar()
        or 0
    )
    failed = (
        db.query(func.count(ScanTask.id))
        .filter(ScanTask.state == "FAILED", ScanTask.created_at >= since)
        .scalar()
        or 0
    )
    total_findings = db.query(func.count(ScanFinding.id)).filter(ScanFinding.created_at >= since).scalar() or 0
    high_findings = (
        db.query(func.count(ScanFinding.id))
        .filter(ScanFinding.severity == "HIGH", ScanFinding.created_at >= since)
        .scalar()
        or 0
    )
    return (
        f"扫描任务 {total_tasks}（完成 {completed} / 失败 {failed}）"
        f"；漏洞总数 {total_findings}（高危 {high_findings}）"
    )


def _extract_summary(markdown: str, default_summary: str) -> str:
    for line in str(markdown or "").splitlines():
        content = line.strip().lstrip("#").strip()
        if content:
            return content[:500]
    return default_summary[:500]


def _write_report_to_disk(report_type: str, content: str, now: datetime) -> str:
    repo_root = Path(__file__).resolve().parents[2]
    report_dir = repo_root / "backend" / "generated_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{report_type}_{uuid.uuid4().hex[:6]}.md"
    full_path = report_dir / filename
    full_path.write_text(content, encoding="utf-8")
    return f"/generated_reports/{filename}"


def _resolve_report_path(detail_path: str | None) -> Path | None:
    if not detail_path:
        return None
    repo_root = Path(__file__).resolve().parents[2]
    rel = detail_path.lstrip("/")
    full = repo_root / "backend" / rel
    if full.is_file():
        return full
    full2 = repo_root / rel
    return full2 if full2.is_file() else None


def _get_file_size(detail_path: str | None) -> int | None:
    p = _resolve_report_path(detail_path)
    return p.stat().st_size if p else None


class GenerateReportRequest(BaseModel):
    report_type: str  # daily, weekly, event, scan
    scope: Optional[str] = None


@router.post("/generate")
async def generate_report(
    req: GenerateReportRequest,
    request: Request,
    current_user: User = Depends(require_permissions("generate_report")),
    db: Session = Depends(get_db),
):
    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    now = _utc_now()

    if req.report_type == "daily":
        since = now - timedelta(days=1)
        label = "日报"
    elif req.report_type == "weekly":
        since = now - timedelta(weeks=1)
        label = "周报"
    elif req.report_type == "scan":
        since = now - timedelta(days=1)
        label = "扫描报告"
    else:
        since = now - timedelta(days=1)
        label = req.report_type

    defense_summary = _build_defense_summary(db, since)
    scan_summary = _build_scan_summary(db, since)
    summary_fallback = f"[{label}] 防御: {defense_summary} | 探测: {scan_summary}"

    payload: Dict[str, Any] = {
        "report_type": req.report_type,
        "label": label,
        "scope": req.scope or "global",
        "since": since.isoformat(),
        "until": now.isoformat(),
        "defense_summary": defense_summary,
        "scan_summary": scan_summary,
    }

    _t0 = time.monotonic()
    ai_result = await ai_engine.generate_report(
        req.report_type,
        payload,
        trace_id=trace_id,
        with_meta=True,
    )
    elapsed_ms = (time.monotonic() - _t0) * 1000
    report_content = str(ai_result.get("text") or "").strip() or summary_fallback
    summary = _extract_summary(report_content, summary_fallback)
    detail_path = _write_report_to_disk(req.report_type, report_content, now)

    report = AIReport(
        report_type=req.report_type,
        scope=req.scope or "全局",
        summary=summary,
        detail_path=detail_path,
        trace_id=trace_id,
    )
    db.add(report)

    prompt_text = json.dumps(payload, ensure_ascii=False)
    decision_log = AIDecisionLog(
        context_type="report",
        model_name=str(ai_result.get("model") or "unknown"),
        decision=ai_result.get("fallback_reason") or "ok",
        confidence=None,
        reason=summary[:500] if summary else None,
        prompt_hash=hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:16],
        inference_ms=round(elapsed_ms, 2),
        model_params=json.dumps({"provider": ai_result.get("provider"), "degraded": ai_result.get("degraded"), "report_type": req.report_type}, ensure_ascii=False),
        trace_id=trace_id,
    )
    db.add(decision_log)
    db.commit()
    db.refresh(report)

    AuditService.log(
        db=db,
        actor=str(current_user.username),
        action="generate_report",
        target=str(report.id),
        target_type="report",
        reason=ai_result.get("fallback_reason"),
        result="success",
        trace_id=trace_id,
    )

    return APIResponse.success(
        {
            "report_id": report.id,
            "summary": summary,
            "detail_path": detail_path,
            "meta": {
                "degraded": bool(ai_result.get("degraded")),
                "fallback_reason": ai_result.get("fallback_reason"),
                "provider": ai_result.get("provider"),
                "model": ai_result.get("model"),
                "trace_id": trace_id,
            },
        },
        message=f"{label}已生成",
        trace_id=trace_id,
    )


@router.get("/reports")
async def get_reports(
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    if page < 1:
        page = 1
    query = db.query(AIReport)
    total = query.count()
    reports = query.order_by(AIReport.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return APIResponse.success(
        {
            "total": total,
            "page": page,
            "items": [
                {
                    "id": item.id,
                    "report_type": item.report_type,
                    "scope": item.scope,
                    "summary": item.summary,
                    "detail_path": item.detail_path,
                    "format": item.format,
                    "trace_id": item.trace_id,
                    "file_size": _get_file_size(item.detail_path),
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
                for item in reports
            ],
        }
    )


@router.get("/reports/{report_id}")
async def get_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(AIReport).filter(AIReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return APIResponse.success(
        {
            "id": report.id,
            "report_type": report.report_type,
            "scope": report.scope,
            "summary": report.summary,
            "detail_path": report.detail_path,
            "format": report.format,
            "trace_id": report.trace_id,
            "file_size": _get_file_size(report.detail_path),
            "created_at": report.created_at.isoformat() if report.created_at else None,
        }
    )


@router.get("/reports/{report_id}/content")
async def get_report_content(report_id: int, db: Session = Depends(get_db)):
    report = db.query(AIReport).filter(AIReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    path = _resolve_report_path(report.detail_path)
    if not path:
        raise HTTPException(status_code=404, detail="Report file not found on disk")
    content = path.read_text(encoding="utf-8")
    return APIResponse.success(
        {
            "id": report.id,
            "report_type": report.report_type,
            "content": content,
            "file_size": path.stat().st_size,
            "created_at": report.created_at.isoformat() if report.created_at else None,
        }
    )

