"""S1-04 Prompt 模板版本管理与审计 API"""
from __future__ import annotations

import difflib
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import require_permissions
from core.database import PromptTemplate, User, get_db
from core.response import APIResponse
from services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/ai/prompt-templates", tags=["prompt-templates"])


class TemplateCreateRequest(BaseModel):
    template_key: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    description: Optional[str] = None


class TemplateUpdateRequest(BaseModel):
    content: str = Field(..., min_length=1)
    description: Optional[str] = None


@router.get("")
async def list_templates(
    template_key: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_ai_sessions")),
):
    """列出 Prompt 模板"""
    query = db.query(PromptTemplate)
    if template_key:
        query = query.filter(PromptTemplate.template_key == template_key)
    if active_only:
        query = query.filter(PromptTemplate.is_active == 1)

    templates = query.order_by(
        PromptTemplate.template_key, PromptTemplate.version.desc()
    ).all()

    return APIResponse.success({
        "total": len(templates),
        "items": [
            {
                "id": t.id,
                "template_key": t.template_key,
                "version": t.version,
                "content": t.content[:200] + "..." if len(t.content) > 200 else t.content,
                "description": t.description,
                "is_active": bool(t.is_active),
                "approved_by": t.approved_by,
                "approved_at": t.approved_at.isoformat() if t.approved_at else None,
                "created_by": t.created_by,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in templates
        ],
    })


@router.get("/{template_id}")
async def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_ai_sessions")),
):
    """查看模板详情（完整内容）"""
    t = db.query(PromptTemplate).filter(PromptTemplate.id == template_id).first()
    if not t:
        raise HTTPException(404, "模板不存在")

    return APIResponse.success({
        "id": t.id,
        "template_key": t.template_key,
        "version": t.version,
        "content": t.content,
        "description": t.description,
        "is_active": bool(t.is_active),
        "approved_by": t.approved_by,
        "approved_at": t.approved_at.isoformat() if t.approved_at else None,
        "created_by": t.created_by,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    })


@router.post("")
async def create_template(
    req: TemplateCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("approve_event")),
):
    """创建新 Prompt 模板（初始版本）"""
    existing = db.query(PromptTemplate).filter(
        PromptTemplate.template_key == req.template_key,
    ).first()
    if existing:
        raise HTTPException(409, f"模板 '{req.template_key}' 已存在，请使用 PUT 更新")

    template = PromptTemplate(
        template_key=req.template_key,
        version=1,
        content=req.content,
        description=req.description,
        is_active=1,
        created_by=current_user.username,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    AuditService.log(
        db=db, actor=current_user.username,
        action="create_prompt_template", target=req.template_key,
        target_type="prompt_template", trace_id=trace_id,
    )

    return APIResponse.success({
        "id": template.id,
        "template_key": template.template_key,
        "version": template.version,
    }, message="模板已创建")


@router.put("/{template_id}")
async def update_template(
    template_id: int,
    req: TemplateUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("approve_event")),
):
    """更新模板（创建新版本，旧版本自动停用）"""
    old = db.query(PromptTemplate).filter(PromptTemplate.id == template_id).first()
    if not old:
        raise HTTPException(404, "模板不存在")

    # 获取当前最大版本号
    max_ver = (
        db.query(PromptTemplate.version)
        .filter(PromptTemplate.template_key == old.template_key)
        .order_by(PromptTemplate.version.desc())
        .first()
    )
    new_version = (max_ver[0] if max_ver else 0) + 1

    # 停用旧版本
    db.query(PromptTemplate).filter(
        PromptTemplate.template_key == old.template_key,
        PromptTemplate.is_active == 1,
    ).update({"is_active": 0})

    # 创建新版本
    new_template = PromptTemplate(
        template_key=old.template_key,
        version=new_version,
        content=req.content,
        description=req.description or old.description,
        is_active=1,
        approved_by=current_user.username,
        approved_at=datetime.now(timezone.utc),
        created_by=current_user.username,
    )
    db.add(new_template)
    db.commit()
    db.refresh(new_template)

    # 计算 diff
    diff = list(difflib.unified_diff(
        old.content.splitlines(keepends=True),
        req.content.splitlines(keepends=True),
        fromfile=f"v{old.version}",
        tofile=f"v{new_version}",
        lineterm="",
    ))
    diff_text = "\n".join(diff[:50])  # 限制diff长度

    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    AuditService.log(
        db=db, actor=current_user.username,
        action="update_prompt_template",
        target=old.template_key,
        target_type="prompt_template",
        reason=f"v{old.version}→v{new_version} | {diff_text[:200]}",
        trace_id=trace_id,
    )

    return APIResponse.success({
        "id": new_template.id,
        "template_key": new_template.template_key,
        "version": new_template.version,
        "diff": diff_text,
    }, message=f"模板已更新至 v{new_version}")


@router.get("/{template_id}/diff")
async def get_template_diff(
    template_id: int,
    compare_version: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_ai_sessions")),
):
    """查看模板版本差异"""
    current = db.query(PromptTemplate).filter(PromptTemplate.id == template_id).first()
    if not current:
        raise HTTPException(404, "模板不存在")

    if compare_version:
        previous = db.query(PromptTemplate).filter(
            PromptTemplate.template_key == current.template_key,
            PromptTemplate.version == compare_version,
        ).first()
    else:
        previous = db.query(PromptTemplate).filter(
            PromptTemplate.template_key == current.template_key,
            PromptTemplate.version == current.version - 1,
        ).first()

    if not previous:
        return APIResponse.success({
            "template_key": current.template_key,
            "current_version": current.version,
            "diff": "(no previous version)",
        })

    diff = list(difflib.unified_diff(
        previous.content.splitlines(keepends=True),
        current.content.splitlines(keepends=True),
        fromfile=f"v{previous.version}",
        tofile=f"v{current.version}",
        lineterm="",
    ))

    return APIResponse.success({
        "template_key": current.template_key,
        "from_version": previous.version,
        "to_version": current.version,
        "diff": "\n".join(diff),
    })


@router.get("/key/{template_key}/versions")
async def list_template_versions(
    template_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_ai_sessions")),
):
    """列出模板所有版本"""
    versions = (
        db.query(PromptTemplate)
        .filter(PromptTemplate.template_key == template_key)
        .order_by(PromptTemplate.version.desc())
        .all()
    )

    if not versions:
        raise HTTPException(404, f"模板 '{template_key}' 不存在")

    return APIResponse.success({
        "template_key": template_key,
        "total_versions": len(versions),
        "items": [
            {
                "id": v.id,
                "version": v.version,
                "is_active": bool(v.is_active),
                "approved_by": v.approved_by,
                "created_by": v.created_by,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ],
    })
