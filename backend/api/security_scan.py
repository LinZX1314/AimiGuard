"""E1-01 CI/CD 安全扫描报告 API"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import require_permissions
from core.database import SecurityScanReport, User, get_db
from core.response import APIResponse

router = APIRouter(prefix="/api/v1/security-scan", tags=["security-scan"])


class SubmitReportRequest(BaseModel):
    scan_tool: str = Field(..., pattern="^(bandit|semgrep|pip-audit)$")
    trigger_type: str = Field("manual", pattern="^(pr|push|manual|scheduled)$")
    branch: Optional[str] = None
    commit_sha: Optional[str] = None
    total_findings: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    findings_json: Optional[str] = None
    passed: bool = True


def _report_to_dict(r: SecurityScanReport) -> dict:
    return {
        "id": r.id,
        "scan_tool": r.scan_tool,
        "trigger_type": r.trigger_type,
        "branch": r.branch,
        "commit_sha": r.commit_sha,
        "total_findings": r.total_findings,
        "high_count": r.high_count,
        "medium_count": r.medium_count,
        "low_count": r.low_count,
        "passed": bool(r.passed),
        "trace_id": r.trace_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/reports")
async def list_reports(
    scan_tool: Optional[str] = Query(None),
    passed: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_events")),
):
    """查询安全扫描报告列表"""
    query = db.query(SecurityScanReport)
    if scan_tool:
        query = query.filter(SecurityScanReport.scan_tool == scan_tool)
    if passed is not None:
        query = query.filter(SecurityScanReport.passed == (1 if passed else 0))

    total = query.count()
    rows = (
        query.order_by(SecurityScanReport.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return APIResponse.success({
        "total": total,
        "page": page,
        "items": [_report_to_dict(r) for r in rows],
    })


@router.post("/reports")
async def submit_report(
    req: SubmitReportRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("approve_event")),
):
    """提交安全扫描报告（CI流水线或手动触发）"""
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))

    report = SecurityScanReport(
        scan_tool=req.scan_tool,
        trigger_type=req.trigger_type,
        branch=req.branch,
        commit_sha=req.commit_sha,
        total_findings=req.total_findings,
        high_count=req.high_count,
        medium_count=req.medium_count,
        low_count=req.low_count,
        findings_json=req.findings_json,
        passed=1 if req.passed else 0,
        trace_id=trace_id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return APIResponse.success(_report_to_dict(report), message="扫描报告已提交")


@router.get("/reports/{report_id}")
async def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_events")),
):
    """获取扫描报告详情（含 findings_json）"""
    report = db.query(SecurityScanReport).filter(SecurityScanReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    result = _report_to_dict(report)
    result["findings_json"] = report.findings_json
    return APIResponse.success(result)
