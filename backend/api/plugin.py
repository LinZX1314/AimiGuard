"""插件注册表管理 API"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import uuid

from core.database import get_db, PluginRegistry, User
from core.response import APIResponse
from api.auth import require_permissions
from services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/plugins", tags=["plugins"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PluginCreate(BaseModel):
    plugin_name: str
    plugin_type: str  # mcp, scanner, notifier, ai_model, threat_intel
    endpoint: Optional[str] = None
    config_json: Optional[str] = None
    enabled: int = 1
    source_url: Optional[str] = None
    publisher_signature: Optional[str] = None
    content_hash: Optional[str] = None


class PluginUpdate(BaseModel):
    plugin_name: Optional[str] = None
    plugin_type: Optional[str] = None
    endpoint: Optional[str] = None
    config_json: Optional[str] = None
    enabled: Optional[int] = None


@router.get("")
async def list_plugins(
    plugin_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_plugins")),
):
    """获取插件列表"""
    query = db.query(PluginRegistry)
    if plugin_type:
        query = query.filter(PluginRegistry.plugin_type == plugin_type)
    plugins = query.order_by(PluginRegistry.created_at.desc()).all()

    return APIResponse.success([
        {
            "id": p.id,
            "plugin_name": p.plugin_name,
            "plugin_type": p.plugin_type,
            "endpoint": p.endpoint,
            "config_json": p.config_json,
            "enabled": p.enabled,
            "created_at": p.created_at.isoformat().replace("+00:00", "Z") if p.created_at else None,
            "updated_at": p.updated_at.isoformat().replace("+00:00", "Z") if p.updated_at else None,
        }
        for p in plugins
    ])


@router.post("")
async def create_plugin(
    data: PluginCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("manage_plugins")),
):
    """注册插件"""
    existing = db.query(PluginRegistry).filter(PluginRegistry.plugin_name == data.plugin_name).first()
    if existing:
        raise HTTPException(400, f"插件 '{data.plugin_name}' 已存在")

    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())

    # S2-01: MCP 插件安全校验
    if data.plugin_type == "mcp" and data.source_url:
        from services.plugin_security import verify_plugin
        is_safe, risk_level, reason = verify_plugin(
            plugin_name=data.plugin_name,
            source_url=data.source_url,
            publisher_signature=data.publisher_signature,
            content_hash=data.content_hash,
        )
        if not is_safe:
            AuditService.log(
                db=db, actor=str(current_user.username),
                action="malicious_plugin_blocked", target=data.plugin_name,
                target_type="plugin", reason=reason,
                result="blocked", trace_id=trace_id,
            )
            raise HTTPException(403, f"插件安全校验失败: {reason}")

    plugin = PluginRegistry(
        plugin_name=data.plugin_name,
        plugin_type=data.plugin_type,
        endpoint=data.endpoint,
        config_json=data.config_json,
        enabled=data.enabled,
    )
    db.add(plugin)
    db.commit()
    db.refresh(plugin)

    AuditService.log(
        db=db, actor=str(current_user.username),
        action="create_plugin", target=data.plugin_name,
        target_type="plugin", trace_id=trace_id,
    )

    return APIResponse.success(
        {"id": plugin.id, "plugin_name": plugin.plugin_name},
        message="插件已注册",
    )


@router.put("/{plugin_id}")
async def update_plugin(
    plugin_id: int,
    data: PluginUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("manage_plugins")),
):
    """更新插件配置"""
    plugin = db.query(PluginRegistry).filter(PluginRegistry.id == plugin_id).first()
    if not plugin:
        raise HTTPException(404, "插件不存在")

    if data.plugin_name is not None:
        plugin.plugin_name = data.plugin_name
    if data.plugin_type is not None:
        plugin.plugin_type = data.plugin_type
    if data.endpoint is not None:
        plugin.endpoint = data.endpoint
    if data.config_json is not None:
        plugin.config_json = data.config_json
    if data.enabled is not None:
        plugin.enabled = data.enabled
    plugin.updated_at = _utc_now()
    db.commit()

    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    AuditService.log(
        db=db, actor=str(current_user.username),
        action="update_plugin", target=str(plugin_id),
        target_type="plugin", trace_id=trace_id,
    )

    return APIResponse.success(None, message="插件已更新")


@router.post("/{plugin_id}/toggle")
async def toggle_plugin(
    plugin_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("manage_plugins")),
):
    """启停插件"""
    plugin = db.query(PluginRegistry).filter(PluginRegistry.id == plugin_id).first()
    if not plugin:
        raise HTTPException(404, "插件不存在")

    plugin.enabled = 0 if plugin.enabled else 1
    plugin.updated_at = _utc_now()
    db.commit()

    action = "enable_plugin" if plugin.enabled else "disable_plugin"
    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    AuditService.log(
        db=db, actor=str(current_user.username),
        action=action, target=plugin.plugin_name,
        target_type="plugin", trace_id=trace_id,
    )

    return APIResponse.success(
        {"enabled": plugin.enabled},
        message=f"插件已{'启用' if plugin.enabled else '禁用'}",
    )


@router.delete("/{plugin_id}")
async def delete_plugin(
    plugin_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("manage_plugins")),
):
    """删除插件"""
    plugin = db.query(PluginRegistry).filter(PluginRegistry.id == plugin_id).first()
    if not plugin:
        raise HTTPException(404, "插件不存在")

    name = plugin.plugin_name
    db.delete(plugin)
    db.commit()

    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    AuditService.log(
        db=db, actor=str(current_user.username),
        action="delete_plugin", target=name,
        target_type="plugin", trace_id=trace_id,
    )

    return APIResponse.success(None, message="插件已删除")


@router.post("/verify")
async def verify_plugin_security(
    data: PluginCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("manage_plugins")),
):
    """S2-01: 预检验插件安全性（不注册）"""
    from services.plugin_security import verify_plugin
    is_safe, risk_level, reason = verify_plugin(
        plugin_name=data.plugin_name,
        source_url=data.source_url or "",
        publisher_signature=data.publisher_signature,
        content_hash=data.content_hash,
    )
    return APIResponse.success({
        "is_safe": is_safe,
        "risk_level": risk_level,
        "reason": reason,
    })


@router.get("/{plugin_id}/permissions")
async def get_plugin_permissions(
    plugin_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_plugins")),
):
    """S2-02: 查看插件权限声明与风险评分"""
    import json as _json
    from services.plugin_sandbox import parse_permissions, compute_risk_score

    plugin = db.query(PluginRegistry).filter(PluginRegistry.id == plugin_id).first()
    if not plugin:
        raise HTTPException(404, "插件不存在")

    perms = parse_permissions(plugin.declared_permissions)
    return APIResponse.success({
        "plugin_id": plugin.id,
        "plugin_name": plugin.plugin_name,
        "declared_permissions": sorted(perms),
        "risk_score": plugin.risk_score or compute_risk_score(list(perms)),
        "valid_permissions": sorted(["read_only", "execute", "network_access", "file_system"]),
    })


@router.put("/{plugin_id}/permissions")
async def update_plugin_permissions(
    plugin_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("manage_plugins")),
):
    """S2-02: 更新插件权限声明"""
    import json as _json
    from services.plugin_sandbox import validate_declared_permissions, compute_risk_score

    plugin = db.query(PluginRegistry).filter(PluginRegistry.id == plugin_id).first()
    if not plugin:
        raise HTTPException(404, "插件不存在")

    body = await request.json()
    permissions = body.get("permissions", [])

    valid, reason = validate_declared_permissions(permissions)
    if not valid:
        raise HTTPException(400, f"权限声明无效: {reason}")

    plugin.declared_permissions = _json.dumps(permissions)
    plugin.risk_score = compute_risk_score(permissions)
    plugin.updated_at = _utc_now()
    db.commit()

    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    AuditService.log(
        db=db, actor=str(current_user.username),
        action="update_plugin_permissions", target=plugin.plugin_name,
        target_type="plugin", reason=str(permissions),
        trace_id=trace_id,
    )

    return APIResponse.success({
        "plugin_id": plugin.id,
        "declared_permissions": permissions,
        "risk_score": plugin.risk_score,
    }, message="插件权限已更新")


@router.get("/blacklist")
async def get_blacklist(
    current_user: User = Depends(require_permissions("manage_plugins")),
):
    """S2-01: 获取恶意MCP服务器黑名单"""
    from services.plugin_security import get_blacklist
    return APIResponse.success({"blacklist": get_blacklist()})
