"""
IP 白名单动态管理 API

功能：
  - 查看当前白名单列表
  - 添加永久/临时白名单条目
  - 删除白名单条目（需 admin 权限 + 审计记录）
  - 自动清理过期临时白名单

接口：
  GET    /api/v1/security/whitelist        — 查看白名单列表
  POST   /api/v1/security/whitelist/add    — 添加永久白名单
  POST   /api/v1/security/whitelist/temp   — 添加临时白名单
  DELETE /api/v1/security/whitelist/{id}   — 删除白名单条目
"""
from __future__ import annotations

import ipaddress
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.auth import require_permissions
from core.database import get_db, User
from services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/security", tags=["security"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class WhitelistAddRequest(BaseModel):
    ip_range: str
    description: str = ""
    whitelist_type: str = "permanent"
    trace_id: str = ""

    @field_validator("ip_range")
    @classmethod
    def validate_ip_range(cls, v: str) -> str:
        try:
            ipaddress.ip_network(v, strict=False)
        except ValueError:
            raise ValueError(f"Invalid CIDR format: {v}")
        return v


class WhitelistTempRequest(BaseModel):
    ip_range: str
    description: str = ""
    expires_in_hours: int = 4
    reason: str = ""
    trace_id: str = ""

    @field_validator("ip_range")
    @classmethod
    def validate_ip_range(cls, v: str) -> str:
        try:
            ipaddress.ip_network(v, strict=False)
        except ValueError:
            raise ValueError(f"Invalid CIDR format: {v}")
        return v


class WhitelistEntry(BaseModel):
    id: int
    ip_range: str
    description: Optional[str] = None
    whitelist_type: str
    expires_at: Optional[str] = None
    created_by: str
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/whitelist")
async def list_whitelist(
    whitelist_type: Optional[str] = None,
    current_user: User = Depends(require_permissions("system:config")),
    db: Session = Depends(get_db),
):
    """查看白名单列表"""
    query = "SELECT id, ip_range, description, whitelist_type, expires_at, created_by, created_at, updated_at FROM ip_whitelist"
    params = {}

    if whitelist_type:
        query += " WHERE whitelist_type = :wt"
        params["wt"] = whitelist_type

    query += " ORDER BY created_at DESC"
    rows = db.execute(text(query), params).fetchall()

    entries = []
    for r in rows:
        entries.append({
            "id": r[0],
            "ip_range": r[1],
            "description": r[2],
            "whitelist_type": r[3],
            "expires_at": r[4],
            "created_by": r[5],
            "created_at": r[6],
            "updated_at": r[7],
        })

    return {"code": 0, "data": entries, "total": len(entries)}


@router.post("/whitelist/add")
async def add_whitelist(
    req: WhitelistAddRequest,
    current_user: User = Depends(require_permissions("system:config")),
    db: Session = Depends(get_db),
):
    """添加永久白名单"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        text(
            "INSERT INTO ip_whitelist (ip_range, description, whitelist_type, created_by, created_at, updated_at) "
            "VALUES (:ip, :desc, 'permanent', :by, :now, :now)"
        ),
        {"ip": req.ip_range, "desc": req.description, "by": current_user.username, "now": now},
    )
    db.commit()

    AuditService.log(
        db=db,
        actor=current_user.username,
        action="whitelist_add",
        target=req.ip_range,
        result="success",
        trace_id=req.trace_id or f"wl_{now}",
    )
    db.commit()

    return {"code": 0, "message": f"已添加白名单: {req.ip_range}"}


@router.post("/whitelist/temp")
async def add_temp_whitelist(
    req: WhitelistTempRequest,
    current_user: User = Depends(require_permissions("system:config")),
    db: Session = Depends(get_db),
):
    """添加临时白名单"""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=req.expires_in_hours)
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    exp_str = expires_at.strftime("%Y-%m-%d %H:%M:%S")

    db.execute(
        text(
            "INSERT INTO ip_whitelist (ip_range, description, whitelist_type, expires_at, created_by, created_at, updated_at) "
            "VALUES (:ip, :desc, 'temporary', :exp, :by, :now, :now)"
        ),
        {"ip": req.ip_range, "desc": req.reason or req.description, "exp": exp_str, "by": current_user.username, "now": now_str},
    )
    db.commit()

    AuditService.log(
        db=db,
        actor=current_user.username,
        action="whitelist_add_temp",
        target=req.ip_range,
        result=f"expires={exp_str}",
        trace_id=req.trace_id or f"wl_temp_{now_str}",
    )
    db.commit()

    return {"code": 0, "message": f"已添加临时白名单: {req.ip_range}，{req.expires_in_hours}小时后过期"}


@router.delete("/whitelist/{entry_id}")
async def delete_whitelist(
    entry_id: int,
    current_user: User = Depends(require_permissions("system:config")),
    db: Session = Depends(get_db),
):
    """删除白名单条目（需 admin 权限 + 审计记录）"""
    row = db.execute(
        text("SELECT ip_range, description FROM ip_whitelist WHERE id = :id"),
        {"id": entry_id},
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="白名单条目不存在")

    ip_range = row[0]
    db.execute(text("DELETE FROM ip_whitelist WHERE id = :id"), {"id": entry_id})
    db.commit()

    AuditService.log(
        db=db,
        actor=current_user.username,
        action="whitelist_delete",
        target=ip_range,
        result="success",
        trace_id=f"wl_del_{entry_id}",
    )
    db.commit()

    return {"code": 0, "message": f"已删除白名单: {ip_range}"}
