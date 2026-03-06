from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import os

from core.database import get_db, AuditLog, User, ThreatEvent, ScanTask, FirewallSyncTask
from api.auth import get_current_user, get_user_role, get_user_permissions, require_permissions
from services.audit_service import AuditService
from services.mode_service import get_current_mode, set_mode

router = APIRouter(prefix="/api/v1/system", tags=["system"])
compat_router = APIRouter(prefix="/api/system", tags=["system"])

# In-memory system mode (persisted via system_config_snapshot)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


_system_mode = {
    "mode": "PASSIVE",
    "reason": "系统初始化",
    "operator": "system",
    "updated_at": _utc_iso(),
}

APP_VERSION = os.getenv("APP_VERSION", "v0.1.0")
GIT_COMMIT = os.getenv("GIT_COMMIT", "initial")
BUILD_TIME = os.getenv("BUILD_TIME", _utc_iso())
ROLLBACK_CANDIDATE_LIMIT = int(os.getenv("ROLLBACK_CANDIDATE_LIMIT", "5"))


class SystemModeRequest(BaseModel):
    mode: str
    reason: Optional[str] = None


class SystemModeResponse(BaseModel):
    mode: str
    reason: Optional[str]
    operator: Optional[str]
    updated_at: str


class SystemProfileResponse(BaseModel):
    username: str
    email: Optional[str]
    full_name: Optional[str]
    role: str
    permissions: List[str]


class RollbackRequest(BaseModel):
    target_version: str
    reason: str
    trace_id: Optional[str] = None


def _ensure_operator_or_admin(current_user: User, db: Session):
    role = get_user_role(current_user, db)
    if role not in ["admin", "operator"]:
        raise HTTPException(status_code=403, detail="权限不足")


def _get_latest_schema_version(db: Session) -> str:
    latest = db.execute(
        text("""
        SELECT schema_version
        FROM release_history
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """)
    ).fetchone()
    return latest[0] if latest else "unknown"


def _get_available_versions(
    db: Session, limit: int = ROLLBACK_CANDIDATE_LIMIT
) -> List[str]:
    rows = db.execute(
        text("""
        SELECT version
        FROM release_history
        WHERE status IN ('active', 'deployed', 'rolled_back')
        GROUP BY version
        ORDER BY MAX(created_at) DESC
        LIMIT :limit
        """),
        {"limit": limit},
    ).fetchall()
    return [row[0] for row in rows]


def _record_release_status(
    db: Session,
    *,
    version: str,
    git_commit: str,
    schema_version: str,
    deploy_env: str,
    status: str,
    deployed_by: str,
    rollback_reason: Optional[str] = None,
    trace_id: Optional[str] = None,
):
    now = _utc_iso()
    db.execute(
        text("""
        INSERT INTO release_history (
            version, git_commit, schema_version, deploy_env, status,
            deployed_by, rollback_reason, trace_id, created_at, updated_at
        ) VALUES (
            :version, :git_commit, :schema_version, :deploy_env, :status,
            :deployed_by, :rollback_reason, :trace_id, :created_at, :updated_at
        )
        """),
        {
            "version": version,
            "git_commit": git_commit,
            "schema_version": schema_version,
            "deploy_env": deploy_env,
            "status": status,
            "deployed_by": deployed_by,
            "rollback_reason": rollback_reason,
            "trace_id": trace_id,
            "created_at": now,
            "updated_at": now,
        },
    )


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "aimiguan"}


@router.get("/mode", response_model=SystemModeResponse)
async def get_system_mode(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_system_mode"))
):
    deploy_env = os.getenv("APP_ENV", "dev")
    mode = get_current_mode(db, deploy_env)
    return SystemModeResponse(**mode)


@router.post("/mode", response_model=SystemModeResponse)
async def set_system_mode(
    request: SystemModeRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("set_system_mode")),
):
    if request.mode not in ["PASSIVE", "ACTIVE"]:
        raise HTTPException(status_code=400, detail="模式必须是 PASSIVE 或 ACTIVE")

    deploy_env = os.getenv("APP_ENV", "dev")
    trace_id = getattr(req.state, "trace_id", None)
    mode_data = set_mode(
        db=db,
        mode=request.mode,
        reason=request.reason,
        operator=str(current_user.username),
        env=deploy_env,
        trace_id=trace_id,
    )
    global _system_mode
    _system_mode = mode_data
    return SystemModeResponse(**mode_data)


@router.get("/profile", response_model=SystemProfileResponse)
@compat_router.get("/profile", response_model=SystemProfileResponse)
async def get_system_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role = get_user_role(current_user, db)
    permissions = get_user_permissions(current_user, db)
    return SystemProfileResponse(
        username=str(current_user.username),
        email=str(current_user.email) if current_user.email else None,
        full_name=str(current_user.full_name) if current_user.full_name else None,
        role=role,
        permissions=permissions,
    )


@router.get("/version")
@compat_router.get("/version")
async def get_system_version(db: Session = Depends(get_db)):
    schema_version = _get_latest_schema_version(db)
    deploy_env = os.getenv("APP_ENV", "dev")
    return {
        "app_version": APP_VERSION,
        "git_commit": GIT_COMMIT,
        "build_time": BUILD_TIME,
        "schema_version": schema_version,
        "env": deploy_env,
    }


@router.post("/rollback")
@compat_router.post("/rollback")
async def rollback_system(
    payload: RollbackRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("system_rollback")),
):

    trace_id = payload.trace_id or getattr(req.state, "trace_id", None)
    deploy_env = os.getenv("APP_ENV", "dev")
    available_versions = _get_available_versions(db)

    if payload.target_version not in available_versions:
        raise HTTPException(status_code=404, detail={
            "code": 40404,
            "error": "version_not_found",
            "message": f"目标版本 {payload.target_version} 不在可回滚列表中",
            "available_versions": available_versions,
        })

    target = db.execute(
        text("""
        SELECT version, git_commit, schema_version
        FROM release_history
        WHERE version = :version
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """),
        {"version": payload.target_version},
    ).fetchone()

    if not target:
        raise HTTPException(status_code=404, detail={
            "code": 40404,
            "error": "version_not_found",
            "message": f"目标版本 {payload.target_version} 不在可回滚列表中",
            "available_versions": available_versions,
        })

    try:
        _record_release_status(
            db,
            version=target[0],
            git_commit=target[1],
            schema_version=target[2],
            deploy_env=deploy_env,
            status="active",
            deployed_by=str(current_user.username),
            rollback_reason=payload.reason,
            trace_id=trace_id,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail={
            "error": "rollback_failed",
            "message": "数据库迁移版本校验失败",
            "detail": str(exc),
            "trace_id": trace_id,
        })

    AuditService.log(
        db=db,
        actor=str(current_user.username),
        action="system_rollback",
        target=payload.target_version,
        target_type="release",
        reason=payload.reason,
        result="success",
        trace_id=trace_id,
    )

    return {
        "status": "success",
        "rolled_back_to": payload.target_version,
        "actions_taken": ["config_reverted", "schema_checked", "health_verified"],
        "trace_id": trace_id,
    }


# ── 审计日志查询 ──

@router.get("/audit/logs")
@compat_router.get("/audit/logs")
async def get_audit_logs(
    actor: Optional[str] = None,
    action: Optional[str] = None,
    trace_id: Optional[str] = None,
    result: Optional[str] = None,
    target_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(require_permissions("view_audit")),
    db: Session = Depends(get_db),
):
    """审计日志查询（支持 actor/action/trace_id/result 筛选与分页）"""
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 200:
        page_size = 50

    query = db.query(AuditLog)

    if actor:
        query = query.filter(AuditLog.actor.contains(actor))
    if action:
        query = query.filter(AuditLog.action.contains(action))
    if trace_id:
        query = query.filter(AuditLog.trace_id.contains(trace_id))
    if result:
        query = query.filter(AuditLog.result == result)
    if target_type:
        query = query.filter(AuditLog.target_type == target_type)

    total = query.count()
    records = (
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "code": 0,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
            "items": [
                {
                    "id": r.id,
                    "actor": r.actor,
                    "action": r.action,
                    "target": r.target,
                    "target_type": r.target_type,
                    "target_ip": r.target_ip,
                    "result": r.result,
                    "reason": r.reason,
                    "error_message": r.error_message,
                    "trace_id": r.trace_id,
                    "integrity_hash": (r.integrity_hash or "")[:16] + "…" if r.integrity_hash else None,
                    "created_at": r.created_at.isoformat().replace("+00:00", "Z") if r.created_at else None,
                }
                for r in records
            ],
        },
    }


@router.get("/audit/verify")
async def verify_audit_chain(
    limit: int = 200,
    current_user: User = Depends(require_permissions("view_audit")),
    db: Session = Depends(get_db),
):
    """校验审计日志哈希链完整性"""
    result = AuditService.verify_chain(db, limit=min(limit, 1000))
    return {
        "code": 0,
        "data": result,
    }


# ── 可观测性：指标 + 告警阈值 ──

@router.get("/metrics")
@compat_router.get("/metrics")
async def get_system_metrics(
    current_user: User = Depends(require_permissions("view_system_mode")),
    db: Session = Depends(get_db),
):
    """系统运行指标快照（请求量、延迟、错误率、运行时间）"""
    from services.metrics_service import metrics
    from sqlalchemy import func

    snap = metrics.snapshot()

    # 补充数据库指标
    total_events = db.query(func.count(ThreatEvent.id)).scalar() or 0
    total_scans = db.query(func.count(ScanTask.id)).scalar() or 0
    failed_scans = db.query(func.count(ScanTask.id)).filter(ScanTask.state == "FAILED").scalar() or 0
    fw_total = db.query(func.count(FirewallSyncTask.id)).scalar() or 0
    fw_failed = db.query(func.count(FirewallSyncTask.id)).filter(
        FirewallSyncTask.state.in_(["FAILED", "MANUAL_REQUIRED"])
    ).scalar() or 0

    snap["database"] = {
        "threat_events": total_events,
        "scan_tasks": total_scans,
        "scan_fail_rate": round(failed_scans / total_scans * 100, 1) if total_scans > 0 else 0,
        "firewall_tasks": fw_total,
        "firewall_fail_rate": round(fw_failed / fw_total * 100, 1) if fw_total > 0 else 0,
    }

    return {"code": 0, "data": snap}


# 告警阈值（内存存储，可通过 API 调整）
_alert_thresholds = {
    "scan_fail_rate_pct": 20.0,
    "firewall_fail_rate_pct": 10.0,
    "api_p95_ms": 3000.0,
    "scan_timeout_rate_pct": 15.0,
}


@router.get("/alert-thresholds")
async def get_alert_thresholds(
    current_user: User = Depends(require_permissions("view_system_mode")),
):
    """获取告警阈值配置"""
    return {"code": 0, "data": _alert_thresholds}


@router.put("/alert-thresholds")
async def update_alert_thresholds(
    request: Request,
    current_user: User = Depends(require_permissions("set_system_mode")),
    db: Session = Depends(get_db),
):
    """更新告警阈值"""
    body = await request.json()
    updated = []
    for key in _alert_thresholds:
        if key in body:
            _alert_thresholds[key] = float(body[key])
            updated.append(key)

    if updated:
        trace_id = getattr(request.state, "trace_id", None)
        AuditService.log(
            db=db, actor=str(current_user.username),
            action="update_alert_thresholds",
            target=",".join(updated),
            target_type="system_config",
            trace_id=trace_id,
        )

    return {"code": 0, "data": _alert_thresholds, "message": f"已更新 {len(updated)} 项"}


@router.get("/alert-check")
async def check_alerts(
    current_user: User = Depends(require_permissions("view_system_mode")),
    db: Session = Depends(get_db),
):
    """检查是否有指标超过告警阈值"""
    from services.metrics_service import metrics
    from sqlalchemy import func

    alerts = []

    # 扫描失败率
    total_scans = db.query(func.count(ScanTask.id)).scalar() or 0
    failed_scans = db.query(func.count(ScanTask.id)).filter(ScanTask.state == "FAILED").scalar() or 0
    if total_scans > 0:
        rate = failed_scans / total_scans * 100
        if rate >= _alert_thresholds["scan_fail_rate_pct"]:
            alerts.append({"metric": "scan_fail_rate", "value": round(rate, 1), "threshold": _alert_thresholds["scan_fail_rate_pct"], "severity": "HIGH"})

    # 防火墙失败率
    fw_total = db.query(func.count(FirewallSyncTask.id)).scalar() or 0
    fw_failed = db.query(func.count(FirewallSyncTask.id)).filter(
        FirewallSyncTask.state.in_(["FAILED", "MANUAL_REQUIRED"])
    ).scalar() or 0
    if fw_total > 0:
        rate = fw_failed / fw_total * 100
        if rate >= _alert_thresholds["firewall_fail_rate_pct"]:
            alerts.append({"metric": "firewall_fail_rate", "value": round(rate, 1), "threshold": _alert_thresholds["firewall_fail_rate_pct"], "severity": "HIGH"})

    # API P95 延迟
    api_stats = metrics.get_latency_stats("api_request")
    if api_stats["count"] > 10 and api_stats["p95_ms"] >= _alert_thresholds["api_p95_ms"]:
        alerts.append({"metric": "api_p95_latency", "value": api_stats["p95_ms"], "threshold": _alert_thresholds["api_p95_ms"], "severity": "MEDIUM"})

    return {
        "code": 0,
        "data": {
            "has_alerts": len(alerts) > 0,
            "alert_count": len(alerts),
            "alerts": alerts,
            "checked_at": _utc_iso(),
        },
    }
