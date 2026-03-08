"""D1-03/04 威胁情报聚合 + 情报看板 API"""
from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from api.auth import require_permissions
from core.database import PluginRegistry, ScanFinding, ThreatEvent, User, get_db
from core.response import APIResponse
from services.threat_intel import (
    ThreatIntelSource,
    check_kev,
    fetch_cisa_kev,
    load_intel_sources_from_plugins,
)

router = APIRouter(prefix="/api/v1/threat-intel", tags=["threat-intel"])


class RegisterIntelSourceRequest(BaseModel):
    plugin_name: str = Field(..., min_length=1)
    endpoint: str = Field(...)
    api_key: Optional[str] = None


class QueryIPRequest(BaseModel):
    ip: str


class QueryCVERequest(BaseModel):
    cve_id: str


@router.post("/sources")
async def register_intel_source(
    req: RegisterIntelSourceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("approve_event")),
):
    """D1-03: 注册威胁情报源插件"""
    existing = db.query(PluginRegistry).filter(
        PluginRegistry.plugin_name == req.plugin_name,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="情报源已存在")

    config = {}
    if req.api_key:
        config["api_key"] = req.api_key

    plugin = PluginRegistry(
        plugin_name=req.plugin_name,
        plugin_type="threat_intel",
        endpoint=req.endpoint,
        config_json=json.dumps(config) if config else None,
        enabled=1,
    )
    db.add(plugin)
    db.commit()
    db.refresh(plugin)

    return APIResponse.success({
        "id": plugin.id,
        "plugin_name": plugin.plugin_name,
        "endpoint": plugin.endpoint,
        "plugin_type": plugin.plugin_type,
    }, message="情报源已注册")


@router.get("/sources")
async def list_intel_sources(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_events")),
):
    """查询已注册的威胁情报源"""
    plugins = db.query(PluginRegistry).filter(
        PluginRegistry.plugin_type == "threat_intel",
    ).all()

    return APIResponse.success({
        "total": len(plugins),
        "items": [
            {
                "id": p.id,
                "plugin_name": p.plugin_name,
                "endpoint": p.endpoint,
                "enabled": bool(p.enabled),
            }
            for p in plugins
        ],
    })


@router.post("/query/ip")
async def query_ip_intel(
    req: QueryIPRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_events")),
):
    """D1-03: 聚合查询多源 IP 情报"""
    sources = load_intel_sources_from_plugins(db)
    results = []
    for src in sources:
        r = await src.query_ip(req.ip)
        results.append(r)

    return APIResponse.success({
        "ip": req.ip,
        "sources_queried": len(sources),
        "results": results,
    })


@router.post("/query/cve")
async def query_cve_intel(
    req: QueryCVERequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_events")),
):
    """D1-03: 聚合查询多源 CVE 情报 + KEV 检查"""
    sources = load_intel_sources_from_plugins(db)
    results = []
    for src in sources:
        r = await src.query_cve(req.cve_id)
        results.append(r)

    in_kev = await check_kev(req.cve_id)

    return APIResponse.success({
        "cve_id": req.cve_id,
        "in_cisa_kev": in_kev,
        "sources_queried": len(sources),
        "results": results,
    })


# ── D1-04: 威胁情报看板 ──

@router.get("/overview")
async def threat_intel_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("view_events")),
):
    """D1-04: 威胁情报看板数据"""
    total_findings = db.query(sqlfunc.count(ScanFinding.id)).scalar() or 0
    enriched_count = db.query(sqlfunc.count(ScanFinding.id)).filter(
        ScanFinding.enriched_at.isnot(None),
    ).scalar() or 0

    cve_findings = db.query(ScanFinding).filter(
        ScanFinding.cve.isnot(None),
        ScanFinding.cve != "",
    ).all()
    unique_cves = {f.cve for f in cve_findings if f.cve}

    epss_top10 = db.query(ScanFinding).filter(
        ScanFinding.epss_score.isnot(None),
    ).order_by(ScanFinding.epss_score.desc()).limit(10).all()

    priority_fix_count = db.query(sqlfunc.count(ScanFinding.id)).filter(
        ScanFinding.epss_score.isnot(None),
        ScanFinding.epss_score >= 0.1,
        ScanFinding.status.in_(["NEW", "CONFIRMED"]),
    ).scalar() or 0

    kev_result = await fetch_cisa_kev()
    kev_ids = kev_result.get("kev_ids", set())
    local_kev_hits = unique_cves & kev_ids

    return APIResponse.success({
        "total_findings": total_findings,
        "enriched_count": enriched_count,
        "unique_cves": len(unique_cves),
        "kev_total": len(kev_ids),
        "kev_local_hits": len(local_kev_hits),
        "kev_hit_cves": list(local_kev_hits)[:20],
        "priority_fix_count": priority_fix_count,
        "epss_top10": [
            {
                "id": f.id,
                "cve": f.cve,
                "epss_score": f.epss_score,
                "cvss_score": f.cvss_score,
                "asset": f.asset,
                "severity": f.severity,
            }
            for f in epss_top10
        ],
    })
