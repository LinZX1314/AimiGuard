"""
Overview 聚合接口
为防御仪表盘和探测仪表盘提供综合指标、趋势和待办统计
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.auth import require_permissions
from core.database import (
    Asset,
    CollectorConfig,
    ExecutionTask,
    ScanFinding,
    ScanTask,
    ThreatEvent,
    User,
    get_db,
)

router = APIRouter(prefix="/api/v1/overview", tags=["overview"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_z(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _config_map(db: Session, collector_type: str) -> Dict[str, str]:
    rows = (
        db.query(CollectorConfig)
        .filter(CollectorConfig.collector_type == collector_type)
        .all()
    )
    return {str(row.config_key): str(row.config_value or "") for row in rows}


def _config_bool(configs: Dict[str, str], key: str = "enabled", default: bool = False) -> bool:
    raw = configs.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _status_item(key: str, name: str, ok: bool, note: str, metric: Optional[str] = None) -> Dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "ok": ok,
        "note": note,
        "metric": metric,
    }


def _build_chain_status(db: Session) -> Dict[str, List[Dict[str, Any]]]:
    now = _utc_now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    hfish_config = _config_map(db, "hfish")
    nmap_config = _config_map(db, "nmap")
    hfish_enabled = _config_bool(hfish_config, default=False)
    nmap_enabled = _config_bool(nmap_config, default=False)

    threat_24h = db.query(func.count(ThreatEvent.id)).filter(
        ThreatEvent.created_at >= last_24h
    ).scalar() or 0
    threat_7d = db.query(func.count(ThreatEvent.id)).filter(
        ThreatEvent.created_at >= last_7d
    ).scalar() or 0
    scored_7d = db.query(func.count(ThreatEvent.id)).filter(
        ThreatEvent.created_at >= last_7d,
        ThreatEvent.ai_score.isnot(None),
    ).scalar() or 0
    unscored_7d = max(threat_7d - scored_7d, 0)

    execution_7d = db.query(func.count(ExecutionTask.id)).filter(
        ExecutionTask.created_at >= last_7d
    ).scalar() or 0
    execution_success_7d = db.query(func.count(ExecutionTask.id)).filter(
        ExecutionTask.created_at >= last_7d,
        ExecutionTask.state == "SUCCESS",
    ).scalar() or 0
    execution_failed_7d = db.query(func.count(ExecutionTask.id)).filter(
        ExecutionTask.created_at >= last_7d,
        ExecutionTask.state.in_(["FAILED", "RETRYING"]),
    ).scalar() or 0
    execution_manual_required = db.query(func.count(ExecutionTask.id)).filter(
        ExecutionTask.state == "MANUAL_REQUIRED"
    ).scalar() or 0

    assets_total = db.query(func.count(Asset.id)).scalar() or 0
    enabled_assets = db.query(func.count(Asset.id)).filter(
        Asset.enabled == 1
    ).scalar() or 0

    scan_total_7d = db.query(func.count(ScanTask.id)).filter(
        ScanTask.created_at >= last_7d
    ).scalar() or 0
    scan_running = db.query(func.count(ScanTask.id)).filter(
        ScanTask.state == "RUNNING"
    ).scalar() or 0
    scan_reported_7d = db.query(func.count(ScanTask.id)).filter(
        ScanTask.created_at >= last_7d,
        ScanTask.state == "REPORTED",
    ).scalar() or 0
    scan_failed_7d = db.query(func.count(ScanTask.id)).filter(
        ScanTask.created_at >= last_7d,
        ScanTask.state.in_(["FAILED", "FAILED_TIMEOUT", "FAILED_PARSE", "UNREACHABLE"]),
    ).scalar() or 0
    findings_7d = db.query(func.count(ScanFinding.id)).filter(
        ScanFinding.created_at >= last_7d
    ).scalar() or 0

    defense = [
        _status_item(
            "hfish_ingest",
            "告警接入（HFish）",
            hfish_enabled and threat_24h > 0,
            "最近 24h 有入站事件" if hfish_enabled and threat_24h > 0 else (
                "HFish 未启用" if not hfish_enabled else "最近 24h 无入站事件"
            ),
            f"24h {threat_24h} 条 / 7d {threat_7d} 条",
        ),
        _status_item(
            "ai_scoring",
            "AI 评分引擎",
            threat_7d > 0 and unscored_7d == 0,
            "评分完整" if threat_7d > 0 and unscored_7d == 0 else (
                "最近 7 天无事件样本" if threat_7d == 0 else f"{unscored_7d} 条事件未评分"
            ),
            f"已评分 {scored_7d}/{threat_7d}",
        ),
        _status_item(
            "approval_execution",
            "审批与执行",
            execution_7d > 0 and execution_manual_required == 0 and execution_failed_7d == 0,
            "执行闭环正常" if execution_7d > 0 and execution_manual_required == 0 and execution_failed_7d == 0 else (
                "最近 7 天无处置任务" if execution_7d == 0 else (
                    f"{execution_manual_required} 条需人工介入" if execution_manual_required > 0 else f"{execution_failed_7d} 条执行异常"
                )
            ),
            f"成功 {execution_success_7d} / 异常 {execution_failed_7d} / 人工 {execution_manual_required}",
        ),
        _status_item(
            "probe_summary",
            "探测扫描",
            nmap_enabled and enabled_assets > 0 and scan_total_7d > 0 and scan_failed_7d == 0,
            "探测链路正常" if nmap_enabled and enabled_assets > 0 and scan_total_7d > 0 and scan_failed_7d == 0 else (
                "Nmap 未启用" if not nmap_enabled else (
                    "无已启用资产" if enabled_assets == 0 else (
                        "最近 7 天无扫描任务" if scan_total_7d == 0 else f"{scan_failed_7d} 条扫描失败"
                    )
                )
            ),
            f"资产 {enabled_assets}/{assets_total} / 任务 {scan_total_7d} / 发现 {findings_7d}",
        ),
    ]

    probe = [
        _status_item(
            "task_scheduler",
            "任务调度器",
            nmap_enabled and enabled_assets > 0,
            "调度配置已就绪" if nmap_enabled and enabled_assets > 0 else (
                "Nmap 未启用" if not nmap_enabled else "无已启用资产"
            ),
            f"已启用资产 {enabled_assets}/{assets_total}",
        ),
        _status_item(
            "scan_executor",
            "扫描执行器",
            scan_total_7d > 0 and scan_failed_7d == 0,
            "最近 7 天执行正常" if scan_total_7d > 0 and scan_failed_7d == 0 else (
                "最近 7 天无执行记录" if scan_total_7d == 0 else f"{scan_failed_7d} 条扫描失败"
            ),
            f"运行中 {scan_running} / 最近 7 天 {scan_total_7d} 条",
        ),
        _status_item(
            "result_ingest",
            "结果入库",
            scan_reported_7d > 0,
            "结果已入库" if scan_reported_7d > 0 else "暂无已完成任务",
            f"已完成 {scan_reported_7d} / 新增发现 {findings_7d}",
        ),
        _status_item(
            "asset_inventory",
            "资产管理",
            enabled_assets > 0,
            "资产池已就绪" if enabled_assets > 0 else (
                "未配置资产" if assets_total == 0 else "资产均已停用"
            ),
            f"已启用 {enabled_assets}/{assets_total}",
        ),
    ]

    return {"defense": defense, "probe": probe}


# ──────────────────────────────────────────────────────────
# GET /api/v1/overview/metrics
# ──────────────────────────────────────────────────────────

@router.get("/metrics")
async def get_metrics(
    request: Request,
    current_user: User = Depends(require_permissions("view_events")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    系统核心指标聚合：
    - 今日新增告警数
    - 待审批事件数
    - 封禁成功数（今日）
    - 总资产数 / 启用资产数
    - 扫描任务数（运行中 / 今日）
    - 漏洞统计（总数 / 高危数）
    """
    now = _utc_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # ── 防御侧 ──
    today_alerts = db.query(func.count(ThreatEvent.id)).filter(
        ThreatEvent.created_at >= today_start
    ).scalar() or 0

    pending_events = db.query(func.count(ThreatEvent.id)).filter(
        ThreatEvent.status == "PENDING"
    ).scalar() or 0

    # 高危（ai_score >= 80）待处理
    high_risk_pending = db.query(func.count(ThreatEvent.id)).filter(
        ThreatEvent.status == "PENDING",
        ThreatEvent.ai_score >= 80,
    ).scalar() or 0

    # 今日封禁成功
    today_blocked = db.query(func.count(ExecutionTask.id)).filter(
        ExecutionTask.state == "SUCCESS",
        ExecutionTask.ended_at >= today_start,
    ).scalar() or 0

    # 执行失败（需人工介入）
    manual_required = db.query(func.count(ExecutionTask.id)).filter(
        ExecutionTask.state == "MANUAL_REQUIRED",
    ).scalar() or 0

    # ── 探测侧 ──
    total_assets = db.query(func.count(Asset.id)).scalar() or 0
    enabled_assets = db.query(func.count(Asset.id)).filter(
        Asset.enabled == 1
    ).scalar() or 0

    running_tasks = db.query(func.count(ScanTask.id)).filter(
        ScanTask.state == "RUNNING"
    ).scalar() or 0

    today_tasks = db.query(func.count(ScanTask.id)).filter(
        ScanTask.created_at >= today_start
    ).scalar() or 0

    total_findings = db.query(func.count(ScanFinding.id)).scalar() or 0
    high_findings = db.query(func.count(ScanFinding.id)).filter(
        ScanFinding.severity == "HIGH"
    ).scalar() or 0
    medium_findings = db.query(func.count(ScanFinding.id)).filter(
        ScanFinding.severity == "MEDIUM"
    ).scalar() or 0

    return {
        "code": 0,
        "data": {
            "defense": {
                "today_alerts": today_alerts,
                "pending_events": pending_events,
                "high_risk_pending": high_risk_pending,
                "today_blocked": today_blocked,
                "manual_required": manual_required,
                # 封禁成功率（今日有告警时计算）
                "block_success_rate": round(today_blocked / today_alerts * 100, 1) if today_alerts > 0 else 0,
            },
            "probe": {
                "total_assets": total_assets,
                "enabled_assets": enabled_assets,
                "running_tasks": running_tasks,
                "today_tasks": today_tasks,
                "total_findings": total_findings,
                "high_findings": high_findings,
                "medium_findings": medium_findings,
            },
            "generated_at": _iso_z(now),
        },
    }


@router.get("/chain-status")
async def get_chain_status(
    current_user: User = Depends(require_permissions("view_events")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    snapshot = _build_chain_status(db)
    return {
        "code": 0,
        "data": {
            "defense": snapshot["defense"],
            "probe": snapshot["probe"],
            "generated_at": _iso_z(_utc_now()),
        },
    }


# ──────────────────────────────────────────────────────────
# GET /api/v1/overview/trends
# ──────────────────────────────────────────────────────────

@router.get("/trends")
async def get_trends(
    range_value: str = Query("7d", alias="range"),
    current_user: User = Depends(require_permissions("view_events")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    趋势数据：
    - 告警趋势（按天）
    - 扫描任务趋势（按天）
    支持 range: 24h / 7d / 30d
    """
    now = _utc_now()

    if range_value == "24h":
        days = 1
        bucket_hours = 1
    elif range_value == "30d":
        days = 30
        bucket_hours = 24
    else:  # 7d
        days = 7
        bucket_hours = 24

    since = now - timedelta(days=days)

    # 告警趋势：按天聚合
    alert_rows = (
        db.query(
            func.date(ThreatEvent.created_at).label("day"),
            func.count(ThreatEvent.id).label("cnt"),
        )
        .filter(ThreatEvent.created_at >= since)
        .group_by(func.date(ThreatEvent.created_at))
        .order_by(func.date(ThreatEvent.created_at))
        .all()
    )

    # 高危告警趋势
    high_alert_rows = (
        db.query(
            func.date(ThreatEvent.created_at).label("day"),
            func.count(ThreatEvent.id).label("cnt"),
        )
        .filter(
            ThreatEvent.created_at >= since,
            ThreatEvent.ai_score >= 80,
        )
        .group_by(func.date(ThreatEvent.created_at))
        .order_by(func.date(ThreatEvent.created_at))
        .all()
    )

    # 扫描任务趋势
    task_rows = (
        db.query(
            func.date(ScanTask.created_at).label("day"),
            func.count(ScanTask.id).label("cnt"),
        )
        .filter(ScanTask.created_at >= since)
        .group_by(func.date(ScanTask.created_at))
        .order_by(func.date(ScanTask.created_at))
        .all()
    )

    def _fill_days(rows: list, since: datetime, days: int) -> List[Dict]:
        """按天补齐缺失的日期（值为 0）"""
        row_map = {str(r.day): r.cnt for r in rows}
        result = []
        for i in range(days):
            day = (since + timedelta(days=i)).strftime("%Y-%m-%d")
            result.append({"date": day, "count": row_map.get(day, 0)})
        return result

    return {
        "code": 0,
        "data": {
            "range": range_value,
            "alert_trend": _fill_days(alert_rows, since, days),
            "high_alert_trend": _fill_days(high_alert_rows, since, days),
            "task_trend": _fill_days(task_rows, since, days),
        },
    }


# ──────────────────────────────────────────────────────────
# GET /api/v1/overview/todos
# ──────────────────────────────────────────────────────────

@router.get("/todos")
async def get_todos(
    current_user: User = Depends(require_permissions("view_events")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    待办摘要：
    - 高优先级待审批事件 Top 5（按 ai_score 降序）
    - 失败任务 Top 5（执行任务 MANUAL_REQUIRED）
    - 高危漏洞发现 Top 5
    """
    # 高优先级待审批事件
    pending_top = (
        db.query(ThreatEvent)
        .filter(ThreatEvent.status == "PENDING")
        .order_by(ThreatEvent.ai_score.desc(), ThreatEvent.created_at.desc())
        .limit(5)
        .all()
    )

    # MANUAL_REQUIRED 任务（需人工介入）
    failed_tasks = (
        db.query(ExecutionTask)
        .filter(ExecutionTask.state == "MANUAL_REQUIRED")
        .order_by(ExecutionTask.updated_at.desc())
        .limit(5)
        .all()
    )

    # 高危漏洞
    high_findings = (
        db.query(ScanFinding)
        .filter(ScanFinding.severity == "HIGH", ScanFinding.status == "NEW")
        .order_by(ScanFinding.created_at.desc())
        .limit(5)
        .all()
    )

    def _event_to_dict(e: ThreatEvent) -> Dict:
        return {
            "id": e.id,
            "ip": e.ip,
            "source": e.source,
            "ai_score": e.ai_score,
            "ai_reason": e.ai_reason,
            "status": e.status,
            "created_at": _iso_z(e.created_at),
        }

    def _task_to_dict(t: ExecutionTask) -> Dict:
        return {
            "id": t.id,
            "event_id": t.event_id,
            "action": t.action,
            "state": t.state,
            "retry_count": t.retry_count,
            "error_message": t.error_message,
            "updated_at": _iso_z(t.updated_at),
        }

    def _finding_to_dict(f: ScanFinding) -> Dict:
        return {
            "id": f.id,
            "asset": f.asset,
            "port": f.port,
            "service": f.service,
            "cve": f.cve,
            "severity": f.severity,
            "status": f.status,
            "created_at": _iso_z(f.created_at),
        }

    return {
        "code": 0,
        "data": {
            "pending_events": [_event_to_dict(e) for e in pending_top],
            "failed_tasks": [_task_to_dict(t) for t in failed_tasks],
            "high_findings": [_finding_to_dict(f) for f in high_findings],
            "counts": {
                "pending_events": db.query(func.count(ThreatEvent.id)).filter(ThreatEvent.status == "PENDING").scalar() or 0,
                "manual_required": db.query(func.count(ExecutionTask.id)).filter(ExecutionTask.state == "MANUAL_REQUIRED").scalar() or 0,
                "high_findings_new": db.query(func.count(ScanFinding.id)).filter(ScanFinding.severity == "HIGH", ScanFinding.status == "NEW").scalar() or 0,
            },
        },
    }


# ──────────────────────────────────────────────────────────
# GET /api/v1/overview/defense-stats
# 防御侧聚合统计（威胁等级分布 / 来源分布 / TOP IP）
# ──────────────────────────────────────────────────────────

@router.get("/defense-stats")
async def get_defense_stats(
    range: str = "7d",
    current_user: User = Depends(require_permissions("view_events")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    防御侧聚合统计（对应 ai_lzx vuetify_index.html 的图表数据）
    - 威胁等级分布
    - 来源/服务分布
    - TOP 10 攻击 IP
    - 7天/24h 告警趋势
    """
    now = _utc_now()
    days = 30 if range == "30d" else (1 if range == "24h" else 7)
    since = now - timedelta(days=days)

    # 威胁等级分布（按 ai_score 分段）
    threat_level_dist = []
    ranges_def = [
        ("CRITICAL", 90, 100),
        ("HIGH", 70, 89),
        ("MEDIUM", 40, 69),
        ("LOW", 0, 39),
    ]
    for label, lo, hi in ranges_def:
        cnt = db.query(func.count(ThreatEvent.id)).filter(
            ThreatEvent.created_at >= since,
            ThreatEvent.ai_score >= lo,
            ThreatEvent.ai_score <= hi,
        ).scalar() or 0
        threat_level_dist.append({"level": label, "count": cnt})

    # 来源/服务分布
    service_rows = (
        db.query(
            ThreatEvent.service_name,
            func.count(ThreatEvent.id).label("cnt"),
        )
        .filter(ThreatEvent.created_at >= since, ThreatEvent.service_name.isnot(None))
        .group_by(ThreatEvent.service_name)
        .order_by(func.count(ThreatEvent.id).desc())
        .limit(10)
        .all()
    )
    service_dist = [
        {"service": r.service_name or "unknown", "count": r.cnt}
        for r in service_rows
    ]

    # TOP 10 攻击 IP
    top_ip_rows = (
        db.query(
            ThreatEvent.ip,
            func.count(ThreatEvent.id).label("cnt"),
            func.max(ThreatEvent.ai_score).label("max_score"),
        )
        .filter(ThreatEvent.created_at >= since)
        .group_by(ThreatEvent.ip)
        .order_by(func.count(ThreatEvent.id).desc())
        .limit(10)
        .all()
    )
    top_ips = [
        {"ip": r.ip, "count": r.cnt, "max_score": r.max_score}
        for r in top_ip_rows
    ]

    # 总计
    total = db.query(func.count(ThreatEvent.id)).filter(
        ThreatEvent.created_at >= since
    ).scalar() or 0

    high_total = db.query(func.count(ThreatEvent.id)).filter(
        ThreatEvent.created_at >= since,
        ThreatEvent.ai_score >= 80,
    ).scalar() or 0

    return {
        "code": 0,
        "data": {
            "range": range,
            "total": total,
            "high_total": high_total,
            "threat_level_dist": threat_level_dist,
            "service_dist": service_dist,
            "top_ips": top_ips,
        },
    }


@router.get("/false-positive-stats")
async def false_positive_stats(
    range: str = Query("7d", pattern="^(24h|7d|30d)$"),
    current_user: User = Depends(require_permissions("view_events")),
    db: Session = Depends(get_db),
):
    """误报率统计（D3-02）"""
    now = _utc_now()
    delta_map = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
    since = now - delta_map[range]

    total = db.query(func.count(ThreatEvent.id)).filter(
        ThreatEvent.created_at >= since
    ).scalar() or 0

    fp_count = db.query(func.count(ThreatEvent.id)).filter(
        ThreatEvent.created_at >= since,
        ThreatEvent.status == "FALSE_POSITIVE",
    ).scalar() or 0

    fp_rate = round(fp_count / total * 100, 1) if total > 0 else 0.0

    source_dist_rows = (
        db.query(
            ThreatEvent.source_vendor,
            func.count(ThreatEvent.id).label("cnt"),
        )
        .filter(
            ThreatEvent.created_at >= since,
            ThreatEvent.status == "FALSE_POSITIVE",
        )
        .group_by(ThreatEvent.source_vendor)
        .order_by(func.count(ThreatEvent.id).desc())
        .limit(10)
        .all()
    )
    source_dist = [
        {"source": r.source_vendor or "unknown", "count": r.cnt}
        for r in source_dist_rows
    ]

    top_fp_ip_rows = (
        db.query(
            ThreatEvent.ip,
            func.count(ThreatEvent.id).label("cnt"),
        )
        .filter(
            ThreatEvent.created_at >= since,
            ThreatEvent.status == "FALSE_POSITIVE",
        )
        .group_by(ThreatEvent.ip)
        .order_by(func.count(ThreatEvent.id).desc())
        .limit(10)
        .all()
    )
    top_fp_ips = [{"ip": r.ip, "count": r.cnt} for r in top_fp_ip_rows]

    return {
        "code": 0,
        "data": {
            "range": range,
            "total_events": total,
            "false_positive_count": fp_count,
            "false_positive_rate": fp_rate,
            "threshold": 20.0,
            "over_threshold": fp_rate > 20.0,
            "source_distribution": source_dist,
            "top_false_positive_ips": top_fp_ips,
        },
    }
