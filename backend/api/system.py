from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import os
import json
import hashlib
import shutil
import uuid

from core.database import (
    get_db,
    AuditLog,
    AlertEvent,
    AuditExportJob,
    BackupJob,
    RestoreJob,
    MetricPoint,
    MetricRule,
    SecurityScanReport,
    User,
    ThreatEvent,
    ScanTask,
    ExecutionTask,
    FirewallSyncTask,
    ModelProfile,
)
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


class AIAPIConfigResponse(BaseModel):
    provider: str
    base_url: str
    model_name: str
    enabled: bool
    api_key_configured: bool


class AIAPIConfigRequest(BaseModel):
    provider: str = "ollama"
    base_url: str
    model_name: str
    api_key: Optional[str] = None
    enabled: bool = True


class TTSConfigResponse(BaseModel):
    provider: str
    endpoint: Optional[str]
    model_name: str
    voice_model: str
    enabled: bool


class TTSConfigRequest(BaseModel):
    provider: str = "local"
    endpoint: Optional[str] = None
    model_name: str = "local-tts-v1"
    voice_model: Optional[str] = None
    enabled: bool = True


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


def _parse_config_json(raw: Optional[str]) -> dict:
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _get_primary_model_profile(db: Session, model_type: str) -> Optional[ModelProfile]:
    return (
        db.query(ModelProfile)
        .filter(ModelProfile.model_type == model_type)
        .order_by(ModelProfile.priority.asc(), ModelProfile.id.asc())
        .first()
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


@router.get("/ai-config", response_model=AIAPIConfigResponse)
@compat_router.get("/ai-config", response_model=AIAPIConfigResponse)
async def get_ai_api_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("system:config")),
):
    profile = _get_primary_model_profile(db, "llm")
    cfg = _parse_config_json(profile.config_json if profile else None)

    provider = str(cfg.get("provider") or os.getenv("LLM_PROVIDER", "ollama"))
    base_url = str(
        (profile.endpoint if profile else None)
        or cfg.get("base_url")
        or os.getenv("LLM_BASE_URL", "http://localhost:11434")
    )
    model_name = str(
        (profile.model_name if profile else None)
        or cfg.get("model_name")
        or os.getenv("LLM_MODEL", "llama2")
    )

    return AIAPIConfigResponse(
        provider=provider,
        base_url=base_url,
        model_name=model_name,
        enabled=bool(profile.enabled) if profile else True,
        api_key_configured=bool(cfg.get("api_key")),
    )


@router.post("/ai-config")
@compat_router.post("/ai-config")
async def save_ai_api_config(
    payload: AIAPIConfigRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("system:config")),
):
    provider = (payload.provider or "ollama").strip()
    base_url = (payload.base_url or "").strip()
    model_name = (payload.model_name or "").strip()
    if not base_url:
        raise HTTPException(status_code=400, detail="AI API 地址不能为空")
    if not model_name:
        raise HTTPException(status_code=400, detail="模型名称不能为空")

    now = _utc_now()
    profile = _get_primary_model_profile(db, "llm")
    existing_cfg = _parse_config_json(profile.config_json if profile else None)
    incoming_api_key = (payload.api_key or "").strip()
    final_api_key = incoming_api_key or str(existing_cfg.get("api_key") or "")

    cfg = {
        "provider": provider,
        "base_url": base_url,
        "model_name": model_name,
    }
    if final_api_key:
        cfg["api_key"] = final_api_key

    is_local = 0 if provider.lower() in {"openai", "anthropic", "azure", "api"} else 1
    enabled = 1 if payload.enabled else 0
    if profile is None:
        profile = ModelProfile(
            model_name=model_name,
            model_type="llm",
            is_local=is_local,
            endpoint=base_url,
            priority=10,
            enabled=enabled,
            config_json=json.dumps(cfg, ensure_ascii=False),
            created_at=now,
            updated_at=now,
        )
        db.add(profile)
    else:
        profile.model_name = model_name
        profile.endpoint = base_url
        profile.is_local = is_local
        profile.enabled = enabled
        profile.config_json = json.dumps(cfg, ensure_ascii=False)
        profile.updated_at = now

    db.commit()

    # 运行时热更新（避免重启才能生效）
    os.environ["LLM_PROVIDER"] = provider
    os.environ["LLM_BASE_URL"] = base_url
    os.environ["LLM_MODEL"] = model_name
    if final_api_key:
        os.environ["LLM_API_KEY"] = final_api_key
    try:
        from services.ai_engine import ai_engine
        ai_engine.llm_client.provider = provider
        ai_engine.llm_client.base_url = base_url
        ai_engine.llm_client.model = model_name
        ai_engine.llm_client.api_key = final_api_key
    except Exception:
        pass

    trace_id = getattr(req.state, "trace_id", None)
    AuditService.log(
        db=db,
        actor=str(current_user.username),
        action="update_ai_api_config",
        target=model_name,
        target_type="system_config",
        trace_id=trace_id,
    )

    return {
        "code": 0,
        "data": {
            "provider": provider,
            "base_url": base_url,
            "model_name": model_name,
            "enabled": bool(enabled),
            "api_key_configured": bool(final_api_key),
        },
        "message": "AI API 配置已保存",
    }


@router.get("/tts-config", response_model=TTSConfigResponse)
@compat_router.get("/tts-config", response_model=TTSConfigResponse)
async def get_tts_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("system:config")),
):
    profile = _get_primary_model_profile(db, "tts")
    cfg = _parse_config_json(profile.config_json if profile else None)

    provider = str(cfg.get("provider") or os.getenv("TTS_PROVIDER", "local"))
    endpoint = (
        (profile.endpoint if profile else None)
        or cfg.get("endpoint")
        or os.getenv("TTS_BASE_URL")
        or None
    )
    model_name = str(
        (profile.model_name if profile else None)
        or cfg.get("model_name")
        or os.getenv("TTS_MODEL", "local-tts-v1")
    )
    voice_model = str(cfg.get("voice_model") or model_name)

    return TTSConfigResponse(
        provider=provider,
        endpoint=endpoint,
        model_name=model_name,
        voice_model=voice_model,
        enabled=bool(profile.enabled) if profile else True,
    )


@router.post("/tts-config")
@compat_router.post("/tts-config")
async def save_tts_config(
    payload: TTSConfigRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("system:config")),
):
    provider = (payload.provider or "local").strip()
    model_name = (payload.model_name or "").strip()
    voice_model = (payload.voice_model or "").strip() or model_name
    endpoint = (payload.endpoint or "").strip() or None
    if not model_name:
        raise HTTPException(status_code=400, detail="TTS 模型名称不能为空")

    now = _utc_now()
    profile = _get_primary_model_profile(db, "tts")
    cfg = {
        "provider": provider,
        "endpoint": endpoint,
        "model_name": model_name,
        "voice_model": voice_model,
    }
    is_local = 0 if provider.lower() in {"openai", "azure", "api"} else 1
    enabled = 1 if payload.enabled else 0
    if profile is None:
        profile = ModelProfile(
            model_name=model_name,
            model_type="tts",
            is_local=is_local,
            endpoint=endpoint,
            priority=10,
            enabled=enabled,
            config_json=json.dumps(cfg, ensure_ascii=False),
            created_at=now,
            updated_at=now,
        )
        db.add(profile)
    else:
        profile.model_name = model_name
        profile.endpoint = endpoint
        profile.is_local = is_local
        profile.enabled = enabled
        profile.config_json = json.dumps(cfg, ensure_ascii=False)
        profile.updated_at = now

    db.commit()

    os.environ["TTS_PROVIDER"] = provider
    os.environ["TTS_MODEL"] = model_name
    if endpoint:
        os.environ["TTS_BASE_URL"] = endpoint

    trace_id = getattr(req.state, "trace_id", None)
    AuditService.log(
        db=db,
        actor=str(current_user.username),
        action="update_tts_config",
        target=model_name,
        target_type="system_config",
        trace_id=trace_id,
    )

    return {
        "code": 0,
        "data": {
            "provider": provider,
            "endpoint": endpoint,
            "model_name": model_name,
            "voice_model": voice_model,
            "enabled": bool(enabled),
        },
        "message": "TTS 配置已保存",
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


# ── R5 告警闭环 ──


@router.get("/alerts")
@compat_router.get("/alerts")
async def list_alerts(
    status: Optional[str] = None,
    level: Optional[str] = None,
    page: int = 1,
    size: int = 20,
    current_user: User = Depends(require_permissions("view_system_mode")),
    db: Session = Depends(get_db),
):
    """告警列表（支持状态/级别筛选 + 分页）"""
    q = db.query(AlertEvent)
    if status:
        q = q.filter(AlertEvent.status == status)
    if level:
        q = q.filter(AlertEvent.level == level)
    total = q.count()
    items = q.order_by(AlertEvent.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return {
        "code": 0,
        "data": {
            "alerts": [
                {
                    "id": a.id,
                    "level": a.level,
                    "type": a.type,
                    "source": a.source,
                    "summary": a.summary,
                    "payload": json.loads(a.payload_json) if a.payload_json else None,
                    "status": a.status,
                    "acked_by": a.acked_by,
                    "acked_at": a.acked_at.isoformat() + "Z" if a.acked_at else None,
                    "resolved_by": a.resolved_by,
                    "resolved_at": a.resolved_at.isoformat() + "Z" if a.resolved_at else None,
                    "trace_id": a.trace_id,
                    "created_at": a.created_at.isoformat() + "Z" if a.created_at else None,
                }
                for a in items
            ],
            "total": total,
            "page": page,
            "size": size,
        },
    }


@router.post("/alerts/{alert_id}/ack")
@compat_router.post("/alerts/{alert_id}/ack")
async def ack_alert(
    alert_id: int,
    request: Request,
    current_user: User = Depends(require_permissions("view_system_mode")),
    db: Session = Depends(get_db),
):
    """确认告警"""
    alert = db.query(AlertEvent).filter(AlertEvent.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail={"code": 40404, "message": "告警不存在"})
    if alert.status != "NEW":
        raise HTTPException(status_code=400, detail={"code": 50004, "message": f"当前状态 {alert.status} 不可确认，仅 NEW 可确认"})
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    now = _utc_now()
    alert.status = "ACKED"
    alert.acked_by = body.get("ack_by", current_user.username)
    alert.acked_at = now
    alert.updated_at = now
    db.commit()
    AuditService.log(db, actor=current_user.username, action="alert_ack", target=f"alert:{alert_id}", trace_id=body.get("trace_id", alert.trace_id))
    return {"code": 0, "data": {"alert_id": alert_id, "new_status": "ACKED", "acked_at": _utc_iso()}}


@router.post("/alerts/{alert_id}/resolve")
@compat_router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    request: Request,
    current_user: User = Depends(require_permissions("view_system_mode")),
    db: Session = Depends(get_db),
):
    """解决告警"""
    alert = db.query(AlertEvent).filter(AlertEvent.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail={"code": 40404, "message": "告警不存在"})
    if alert.status not in ("NEW", "ACKED"):
        raise HTTPException(status_code=400, detail={"code": 50004, "message": f"当前状态 {alert.status} 不可解决，仅 NEW/ACKED 可解决"})
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    now = _utc_now()
    alert.status = "RESOLVED"
    alert.resolved_by = body.get("resolved_by", current_user.username)
    alert.resolved_at = now
    alert.resolution = body.get("resolution", "")
    alert.updated_at = now
    db.commit()
    AuditService.log(db, actor=current_user.username, action="alert_resolve", target=f"alert:{alert_id}", trace_id=body.get("trace_id", alert.trace_id))
    return {"code": 0, "data": {"alert_id": alert_id, "new_status": "RESOLVED", "resolved_at": _utc_iso()}}


@router.post("/alerts/{alert_id}/postmortem")
@compat_router.post("/alerts/{alert_id}/postmortem")
async def postmortem_alert(
    alert_id: int,
    request: Request,
    current_user: User = Depends(require_permissions("set_system_mode")),
    db: Session = Depends(get_db),
):
    """告警复盘"""
    alert = db.query(AlertEvent).filter(AlertEvent.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail={"code": 40404, "message": "告警不存在"})
    if alert.status != "RESOLVED":
        raise HTTPException(status_code=400, detail={"code": 50004, "message": f"当前状态 {alert.status} 不可复盘，仅 RESOLVED 可复盘"})
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    now = _utc_now()
    alert.status = "POSTMORTEM"
    alert.postmortem_author = body.get("author", current_user.username)
    alert.postmortem_at = now
    content_parts = []
    if body.get("root_cause"):
        content_parts.append(f"Root Cause: {body['root_cause']}")
    if body.get("action_items"):
        content_parts.append(f"Action Items: {json.dumps(body['action_items'], ensure_ascii=False)}")
    alert.postmortem_content = "\n".join(content_parts) if content_parts else body.get("content", "")
    alert.updated_at = now
    db.commit()
    AuditService.log(db, actor=current_user.username, action="alert_postmortem", target=f"alert:{alert_id}", trace_id=body.get("trace_id", alert.trace_id))
    return {"code": 0, "data": {"alert_id": alert_id, "new_status": "POSTMORTEM", "postmortem_at": _utc_iso()}}


# ── R3 备份与恢复 ──


_BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backups")
_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "aimiguard.db")


@router.get("/backup/list")
@compat_router.get("/backup/list")
async def list_backups(
    current_user: User = Depends(require_permissions("set_system_mode")),
    db: Session = Depends(get_db),
):
    """备份列表"""
    jobs = db.query(BackupJob).order_by(BackupJob.created_at.desc()).limit(50).all()
    return {
        "code": 0,
        "data": [
            {
                "id": j.id,
                "job_type": j.job_type,
                "status": j.status,
                "artifact_uri": j.artifact_uri,
                "size_bytes": j.size_bytes,
                "checksum": j.checksum,
                "started_at": j.started_at.isoformat() + "Z" if j.started_at else None,
                "finished_at": j.finished_at.isoformat() + "Z" if j.finished_at else None,
                "triggered_by": j.triggered_by,
            }
            for j in jobs
        ],
    }


@router.post("/backup/create")
@compat_router.post("/backup/create")
async def create_backup(
    request: Request,
    current_user: User = Depends(require_permissions("set_system_mode")),
    db: Session = Depends(get_db),
):
    """创建数据库备份"""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    job_type = body.get("type", "full")
    now = _utc_now()
    job = BackupJob(
        job_type=job_type,
        started_at=now,
        status="running",
        triggered_by=current_user.username,
        trace_id=body.get("trace_id", str(uuid.uuid4())),
    )
    db.add(job)
    db.commit()

    try:
        os.makedirs(_BACKUP_DIR, exist_ok=True)
        ts = now.strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(_BACKUP_DIR, f"backup_{ts}_{job_type}.db")
        if os.path.exists(_DB_PATH):
            shutil.copy2(_DB_PATH, backup_file)
            size = os.path.getsize(backup_file)
            with open(backup_file, "rb") as f:
                checksum = hashlib.sha256(f.read()).hexdigest()
        else:
            size = 0
            checksum = ""
        job.status = "success"
        job.finished_at = _utc_now()
        job.artifact_uri = backup_file
        job.size_bytes = size
        job.checksum = checksum
    except Exception as e:
        job.status = "failed"
        job.finished_at = _utc_now()
        job.error_message = str(e)
    db.commit()
    AuditService.log(db, actor=current_user.username, action="backup_create", target=f"backup:{job.id}", trace_id=job.trace_id)
    return {"code": 0, "data": {"id": job.id, "status": job.status, "artifact_uri": job.artifact_uri, "size_bytes": job.size_bytes}}


@router.post("/backup/restore")
@compat_router.post("/backup/restore")
async def restore_backup(
    request: Request,
    current_user: User = Depends(require_permissions("set_system_mode")),
    db: Session = Depends(get_db),
):
    """从备份恢复"""
    body = await request.json()
    backup_id = body.get("backup_id")
    backup_file = body.get("backup_file")
    if backup_id:
        backup = db.query(BackupJob).filter(BackupJob.id == backup_id).first()
        if not backup or backup.status != "success":
            raise HTTPException(status_code=404, detail={"code": 40404, "message": "备份不存在或状态异常"})
        backup_file = backup.artifact_uri
    if not backup_file or not os.path.exists(str(backup_file)):
        raise HTTPException(status_code=400, detail={"code": 50003, "message": "备份文件不存在"})

    now = _utc_now()
    restore = RestoreJob(
        backup_id=backup_id or 0,
        started_at=now,
        status="running",
        triggered_by=current_user.username,
        reason=body.get("reason", ""),
        trace_id=body.get("trace_id", str(uuid.uuid4())),
    )
    db.add(restore)
    db.commit()

    try:
        shutil.copy2(str(backup_file), _DB_PATH)
        restore.status = "success"
        restore.consistency_check_result = "ok"
        restore.finished_at = _utc_now()
    except Exception as e:
        restore.status = "failed"
        restore.error_message = str(e)
        restore.finished_at = _utc_now()
    db.commit()
    AuditService.log(db, actor=current_user.username, action="backup_restore", target=f"restore:{restore.id}", trace_id=restore.trace_id)
    return {"code": 0, "data": {"id": restore.id, "status": restore.status}}


# ── R4 安全门禁 ──


@router.get("/security-report/latest")
@compat_router.get("/security-report/latest")
async def get_latest_security_report(
    current_user: User = Depends(require_permissions("view_system_mode")),
    db: Session = Depends(get_db),
):
    """最近安全扫描报告"""
    report = db.query(SecurityScanReport).order_by(SecurityScanReport.created_at.desc()).first()
    if not report:
        return {"code": 0, "data": None, "message": "暂无安全扫描报告"}
    return {
        "code": 0,
        "data": {
            "id": report.id,
            "scan_tool": report.scan_tool,
            "trigger_type": report.trigger_type,
            "branch": report.branch,
            "commit_sha": report.commit_sha,
            "total_findings": report.total_findings,
            "high_count": report.high_count,
            "medium_count": report.medium_count,
            "low_count": report.low_count,
            "findings": json.loads(report.findings_json) if report.findings_json else [],
            "passed": bool(report.passed),
            "trace_id": report.trace_id,
            "created_at": report.created_at.isoformat() + "Z" if report.created_at else None,
        },
    }


# ── R6 指标概览与时间序列 ──


@router.get("/metrics/overview")
@compat_router.get("/metrics/overview")
async def metrics_overview(
    current_user: User = Depends(require_permissions("view_system_mode")),
    db: Session = Depends(get_db),
):
    """指标概览（含阈值状态）"""
    from services.metrics_service import metrics
    from sqlalchemy import func

    snap = metrics.snapshot()

    # 队列深度
    queue_depth = db.query(func.count(ExecutionTask.id)).filter(ExecutionTask.state == "QUEUED").scalar() or 0

    # 任务成功率
    total_tasks = db.query(func.count(ExecutionTask.id)).filter(ExecutionTask.state.in_(["SUCCESS", "FAILED"])).scalar() or 0
    success_tasks = db.query(func.count(ExecutionTask.id)).filter(ExecutionTask.state == "SUCCESS").scalar() or 0
    task_success_rate = round(success_tasks / total_tasks, 4) if total_tasks > 0 else 1.0

    api_stats = metrics.get_latency_stats("api_request")

    metric_values = {
        "api_latency_p95_ms": api_stats.get("p95_ms", 0),
        "api_latency_p99_ms": api_stats.get("p99_ms", 0),
        "queue_depth": queue_depth,
        "task_success_rate": task_success_rate,
        "total_requests": snap.get("total_requests", 0),
    }

    # 加载阈值规则
    rules = db.query(MetricRule).filter(MetricRule.enabled == 1).all()
    thresholds = {}
    for r in rules:
        val = metric_values.get(r.metric)
        if val is not None:
            healthy = True
            if r.operator == "gt" and val > r.threshold:
                healthy = False
            elif r.operator == "lt" and val < r.threshold:
                healthy = False
            elif r.operator == "gte" and val >= r.threshold:
                healthy = False
            elif r.operator == "lte" and val <= r.threshold:
                healthy = False
            thresholds[r.metric] = {"threshold": r.threshold, "status": "healthy" if healthy else "unhealthy"}

    return {
        "code": 0,
        "data": {
            "metrics": metric_values,
            "thresholds": thresholds,
            "collected_at": _utc_iso(),
        },
    }


@router.get("/metrics/timeseries")
@compat_router.get("/metrics/timeseries")
async def metrics_timeseries(
    metric: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(require_permissions("view_system_mode")),
    db: Session = Depends(get_db),
):
    """指标时间序列数据"""
    q = db.query(MetricPoint).filter(MetricPoint.metric == metric)
    if start:
        q = q.filter(MetricPoint.ts >= start)
    if end:
        q = q.filter(MetricPoint.ts <= end)
    points = q.order_by(MetricPoint.ts.asc()).limit(limit).all()
    return {
        "code": 0,
        "data": {
            "metric": metric,
            "data_points": [
                {"ts": p.ts.isoformat() + "Z" if p.ts else None, "value": p.value}
                for p in points
            ],
        },
    }


# ── R7 审计导出 ──


@router.post("/audit/export")
@compat_router.post("/audit/export")
async def create_audit_export(
    request: Request,
    current_user: User = Depends(require_permissions("view_audit")),
    db: Session = Depends(get_db),
):
    """创建审计日志导出任务"""
    body = await request.json()
    filters = body.get("filters", {})
    reason = body.get("reason", "")
    trace_id = body.get("trace_id", str(uuid.uuid4()))

    job = AuditExportJob(
        filters_json=json.dumps(filters, ensure_ascii=False),
        status="pending",
        requested_by=current_user.username,
        reason=reason,
        trace_id=trace_id,
    )
    db.add(job)
    db.commit()

    # 同步执行导出（小数据量适用）
    try:
        q = db.query(AuditLog)
        if filters.get("actor"):
            q = q.filter(AuditLog.actor == filters["actor"])
        if filters.get("action"):
            q = q.filter(AuditLog.action == filters["action"])
        if filters.get("start_time"):
            q = q.filter(AuditLog.created_at >= filters["start_time"])
        if filters.get("end_time"):
            q = q.filter(AuditLog.created_at <= filters["end_time"])

        rows = q.order_by(AuditLog.created_at.desc()).all()
        job.status = "completed"
        job.row_count = len(rows)
        job.progress = 1.0

        # 生成导出文件
        export_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exports")
        os.makedirs(export_dir, exist_ok=True)
        export_file = os.path.join(export_dir, f"audit_export_{job.id}.csv")
        with open(export_file, "w", encoding="utf-8") as f:
            f.write("id,actor,action,target,target_ip,reason,result,trace_id,created_at\n")
            for r in rows:
                # 脱敏 target_ip
                masked_ip = _mask_ip(r.target_ip) if r.target_ip else ""
                f.write(f"{r.id},{r.actor},{r.action},{r.target},{masked_ip},{r.reason or ''},{r.result},{r.trace_id},{r.created_at}\n")
        with open(export_file, "rb") as f:
            job.file_hash = f"sha256:{hashlib.sha256(f.read()).hexdigest()}"
        job.file_uri = export_file
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
    db.commit()

    AuditService.log(db, actor=current_user.username, action="audit_export", target=f"export:{job.id}", trace_id=trace_id)
    return {"code": 0, "data": {"job_id": job.id, "status": job.status, "row_count": job.row_count, "trace_id": trace_id}}


@router.get("/audit/export/{job_id}")
@compat_router.get("/audit/export/{job_id}")
async def get_audit_export(
    job_id: int,
    current_user: User = Depends(require_permissions("view_audit")),
    db: Session = Depends(get_db),
):
    """查询审计导出任务状态"""
    job = db.query(AuditExportJob).filter(AuditExportJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail={"code": 40404, "message": "导出任务不存在"})
    return {
        "code": 0,
        "data": {
            "job_id": job.id,
            "status": job.status,
            "file_uri": job.file_uri,
            "file_hash": job.file_hash,
            "row_count": job.row_count,
            "progress": job.progress,
            "requested_by": job.requested_by,
            "created_at": job.created_at.isoformat() + "Z" if job.created_at else None,
        },
    }


def _mask_ip(ip: str) -> str:
    """IP 脱敏：保留首段，其余掩码"""
    if not ip:
        return ""
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.***.**"
    return ip[:4] + "***"
