"""防火墙同步 API — 签名校验、幂等键、回执处理、失败重试"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import hashlib
import hmac
import uuid
import os

from core.database import get_db, FirewallSyncTask, User, CollectorConfig
from core.response import APIResponse
from api.auth import require_permissions, require_role
from services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/firewall", tags=["firewall"])

FIREWALL_SIGN_SECRET = os.getenv("FIREWALL_SIGN_SECRET", "aimiguan-fw-secret-default")
MAX_RETRY = 3


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_z(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat().replace("+00:00", "Z") if dt else None


def _compute_request_hash(ip: str, action: str, vendor: str) -> str:
    return hashlib.sha256(f"{ip}:{action}:{vendor}".encode()).hexdigest()


def _to_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _to_int(value: Optional[str], default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except Exception:
        return default


def _get_config_row(db: Session, key: str) -> Optional[CollectorConfig]:
    return db.query(CollectorConfig).filter(
        CollectorConfig.collector_type == "firewall",
        CollectorConfig.config_key == key,
    ).first()


def _get_config_value(db: Session, key: str) -> Optional[str]:
    row = _get_config_row(db, key)
    return row.config_value if row else None


def _upsert_config(
    db: Session,
    key: str,
    value: str,
    *,
    is_sensitive: int = 0,
    enabled: int = 1,
    description: Optional[str] = None,
) -> None:
    row = _get_config_row(db, key)
    if row:
        row.config_value = value
        row.is_sensitive = is_sensitive
        row.enabled = enabled
        if description:
            row.description = description
        row.updated_at = _utc_now()
        return

    db.add(CollectorConfig(
        collector_type="firewall",
        config_key=key,
        config_value=value,
        is_sensitive=is_sensitive,
        enabled=enabled,
        description=description,
    ))


def _load_firewall_config(db: Session) -> dict:
    """读取防火墙动态配置（缺失时返回默认值）"""
    default_vendor = _get_config_value(db, "default_vendor") or "generic"
    return {
        "enabled": _to_bool(_get_config_value(db, "enabled"), True),
        "api_base_url": _get_config_value(db, "api_base_url"),
        "default_vendor": default_vendor,
        "default_policy_id": _get_config_value(db, "default_policy_id"),
        "timeout_seconds": _to_int(_get_config_value(db, "timeout_seconds"), 10),
        "sign_secret": _get_config_value(db, "sign_secret") or FIREWALL_SIGN_SECRET,
        "has_custom_sign_secret": _get_config_value(db, "sign_secret") is not None,
    }


def _compute_signature(payload: str, sign_secret: str) -> str:
    """HMAC-SHA256 签名"""
    return hmac.new(sign_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _verify_signature(payload: str, provided_sig: str, sign_secret: str) -> bool:
    expected = _compute_signature(payload, sign_secret)
    return hmac.compare_digest(expected, provided_sig)


class FirewallSyncRequest(BaseModel):
    ip: str
    action: str  # block, unblock
    firewall_vendor: Optional[str] = "generic"
    policy_id: Optional[str] = None
    reason: Optional[str] = None


class FirewallReceiptRequest(BaseModel):
    state: str  # SUCCESS, FAILED
    response_digest: Optional[str] = None
    error_message: Optional[str] = None
    signature: Optional[str] = None


class FirewallConfigResponse(BaseModel):
    enabled: bool = True
    api_base_url: Optional[str] = None
    default_vendor: str = "generic"
    default_policy_id: Optional[str] = None
    timeout_seconds: int = 10
    has_custom_sign_secret: bool = False


class FirewallConfigRequest(BaseModel):
    enabled: bool = True
    api_base_url: Optional[str] = None
    default_vendor: str = "generic"
    default_policy_id: Optional[str] = None
    timeout_seconds: int = 10
    sign_secret: Optional[str] = None  # 留空表示不修改


@router.get("/config", response_model=FirewallConfigResponse)
async def get_firewall_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """获取防火墙动态配置"""
    cfg = _load_firewall_config(db)
    return FirewallConfigResponse(
        enabled=cfg["enabled"],
        api_base_url=cfg["api_base_url"],
        default_vendor=cfg["default_vendor"],
        default_policy_id=cfg["default_policy_id"],
        timeout_seconds=cfg["timeout_seconds"],
        has_custom_sign_secret=cfg["has_custom_sign_secret"],
    )


@router.post("/config")
async def save_firewall_config(
    config: FirewallConfigRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """保存防火墙动态配置"""
    if config.timeout_seconds < 1 or config.timeout_seconds > 300:
        raise HTTPException(400, "timeout_seconds 必须在 1~300 之间")

    default_vendor = (config.default_vendor or "generic").strip() or "generic"
    _upsert_config(db, "enabled", "true" if config.enabled else "false", description="是否启用防火墙联动")
    _upsert_config(db, "api_base_url", (config.api_base_url or "").strip(), description="防火墙 API 基础地址")
    _upsert_config(db, "default_vendor", default_vendor, description="默认防火墙厂商")
    _upsert_config(
        db,
        "default_policy_id",
        (config.default_policy_id or "").strip(),
        description="默认策略 ID",
    )
    _upsert_config(
        db,
        "timeout_seconds",
        str(config.timeout_seconds),
        description="防火墙请求超时时间（秒）",
    )
    if config.sign_secret is not None and config.sign_secret.strip():
        _upsert_config(
            db,
            "sign_secret",
            config.sign_secret.strip(),
            is_sensitive=1,
            description="防火墙回执签名密钥",
        )

    db.commit()

    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    AuditService.log(
        db=db,
        actor=str(current_user.username),
        action="save_firewall_config",
        target="firewall_config",
        target_type="collector_config",
        result="success",
        trace_id=trace_id,
    )

    return APIResponse.success(message="防火墙配置已保存")


@router.post("/sync")
async def sync_to_firewall(
    req: FirewallSyncRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("firewall_sync")),
):
    """创建防火墙同步任务（带幂等键）"""
    cfg = _load_firewall_config(db)
    if not cfg["enabled"]:
        raise HTTPException(400, "防火墙同步未启用，请先在联动配置中开启")

    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    vendor = (req.firewall_vendor or cfg["default_vendor"] or "generic").strip() or "generic"
    policy_id = (req.policy_id or cfg["default_policy_id"] or None)
    request_hash = _compute_request_hash(req.ip, req.action, vendor)

    existing = db.query(FirewallSyncTask).filter(
        FirewallSyncTask.request_hash == request_hash,
        FirewallSyncTask.state.in_(["PENDING", "SUCCESS"]),
    ).first()

    if existing:
        return APIResponse.success(
            {"task_id": existing.id, "state": existing.state, "idempotent": True},
            message="任务已存在（幂等命中）",
        )

    task = FirewallSyncTask(
        ip=req.ip,
        firewall_vendor=vendor,
        policy_id=policy_id,
        action=req.action,
        request_hash=request_hash,
        state="PENDING",
        trace_id=trace_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    sig = _compute_signature(f"{task.id}:{req.ip}:{req.action}", cfg["sign_secret"])

    AuditService.log(
        db=db, actor=str(current_user.username),
        action="firewall_sync_create", target=req.ip,
        target_type="firewall_task", target_ip=req.ip,
        reason=req.reason, trace_id=trace_id,
    )

    try:
        from services.metrics_service import metrics
        metrics.inc("firewall_sync_total")
    except Exception:
        pass

    return APIResponse.success(
        {
            "task_id": task.id,
            "request_hash": request_hash,
            "signature": sig,
            "trace_id": trace_id,
        },
        message="防火墙同步任务已创建",
    )


@router.post("/tasks/{task_id}/receipt")
async def process_receipt(
    task_id: int,
    receipt: FirewallReceiptRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("firewall_sync")),
):
    """处理防火墙回执（签名校验 + 状态更新）"""
    cfg = _load_firewall_config(db)
    task = db.query(FirewallSyncTask).filter(FirewallSyncTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")

    if task.state in ("SUCCESS", "MANUAL_REQUIRED"):
        return APIResponse.success(
            {"task_id": task.id, "state": task.state},
            message="任务已终态，无需重复处理",
        )

    # 签名校验（可选但推荐）
    if receipt.signature:
        payload = f"{task_id}:{task.ip}:{task.action}"
        if not _verify_signature(payload, receipt.signature, cfg["sign_secret"]):
            raise HTTPException(403, "签名校验失败")

    trace_id = getattr(request.state, "trace_id", None) or task.trace_id
    now = _utc_now()

    if receipt.state == "SUCCESS":
        task.state = "SUCCESS"
        task.response_digest = receipt.response_digest
        task.updated_at = now
    elif receipt.state == "FAILED":
        task.retry_count = (task.retry_count or 0) + 1
        if task.retry_count >= MAX_RETRY:
            task.state = "MANUAL_REQUIRED"
        else:
            task.state = "FAILED"
        task.error_message = receipt.error_message
        task.updated_at = now
    else:
        raise HTTPException(400, f"无效状态: {receipt.state}，可选 SUCCESS/FAILED")

    db.commit()

    AuditService.log(
        db=db, actor=str(current_user.username),
        action="firewall_receipt",
        target=str(task_id),
        target_type="firewall_task",
        target_ip=task.ip,
        result=task.state,
        error_message=receipt.error_message,
        trace_id=trace_id,
    )

    return APIResponse.success(
        {
            "task_id": task.id,
            "state": task.state,
            "retry_count": task.retry_count,
            "manual_required": task.state == "MANUAL_REQUIRED",
        },
        message=f"回执已处理，任务状态: {task.state}",
    )


@router.post("/tasks/{task_id}/retry")
async def retry_task(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("firewall_sync")),
):
    """手动重试失败/人工介入的任务"""
    task = db.query(FirewallSyncTask).filter(FirewallSyncTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")

    if task.state not in ("FAILED", "MANUAL_REQUIRED"):
        raise HTTPException(400, f"当前状态 {task.state} 不允许重试")

    task.state = "PENDING"
    task.error_message = None
    task.updated_at = _utc_now()
    db.commit()

    trace_id = getattr(request.state, "trace_id", None) or task.trace_id
    AuditService.log(
        db=db, actor=str(current_user.username),
        action="firewall_retry", target=str(task_id),
        target_type="firewall_task", target_ip=task.ip,
        trace_id=trace_id,
    )

    return APIResponse.success(
        {"task_id": task.id, "state": task.state, "retry_count": task.retry_count},
        message="任务已重置为待处理",
    )


@router.get("/tasks")
async def list_firewall_tasks(
    state: Optional[str] = None,
    ip: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_firewall_tasks")),
):
    """防火墙同步任务列表（支持筛选 + 分页）"""
    if page < 1:
        page = 1

    query = db.query(FirewallSyncTask)
    if state:
        query = query.filter(FirewallSyncTask.state == state)
    if ip:
        query = query.filter(FirewallSyncTask.ip.contains(ip))

    total = query.count()
    tasks = (
        query.order_by(FirewallSyncTask.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return APIResponse.success({
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": t.id,
                "ip": t.ip,
                "firewall_vendor": t.firewall_vendor,
                "policy_id": t.policy_id,
                "action": t.action,
                "request_hash": t.request_hash[:16] + "…",
                "state": t.state,
                "retry_count": t.retry_count,
                "response_digest": t.response_digest,
                "error_message": t.error_message,
                "trace_id": t.trace_id,
                "created_at": _iso_z(t.created_at),
                "updated_at": _iso_z(t.updated_at),
            }
            for t in tasks
        ],
    })


@router.get("/tasks/{task_id}")
async def get_firewall_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_firewall_tasks")),
):
    """获取防火墙同步任务详情"""
    task = db.query(FirewallSyncTask).filter(FirewallSyncTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")

    return APIResponse.success({
        "id": task.id,
        "ip": task.ip,
        "firewall_vendor": task.firewall_vendor,
        "policy_id": task.policy_id,
        "action": task.action,
        "request_hash": task.request_hash,
        "state": task.state,
        "retry_count": task.retry_count,
        "response_digest": task.response_digest,
        "error_message": task.error_message,
        "trace_id": task.trace_id,
        "created_at": _iso_z(task.created_at),
        "updated_at": _iso_z(task.updated_at),
    })
