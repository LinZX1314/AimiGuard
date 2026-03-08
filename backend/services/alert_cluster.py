"""
D3-03 告警聚类降噪
策略：(attack_ip, attack_type, time_bucket_1h) 相同则合并，合并后 attack_count 累加。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from core.database import ThreatEvent


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _time_bucket(dt: datetime, bucket_hours: int = 1) -> str:
    """将时间截断到 bucket_hours 小时粒度"""
    ts = dt.replace(minute=0, second=0, microsecond=0)
    hour = ts.hour - (ts.hour % bucket_hours)
    ts = ts.replace(hour=hour)
    return ts.strftime("%Y-%m-%d %H:00")


def cluster_events(
    db: Session,
    hours: int = 24,
    bucket_hours: int = 1,
) -> List[Dict[str, Any]]:
    """
    对最近 hours 小时内的告警做聚类。
    聚类键: (ip, threat_label, time_bucket)
    返回聚类列表，每条包含代表事件和聚类内事件数。
    """
    since = _utc_now() - timedelta(hours=hours)

    events = (
        db.query(ThreatEvent)
        .filter(ThreatEvent.created_at >= since)
        .order_by(ThreatEvent.created_at.desc())
        .all()
    )

    clusters: Dict[str, Dict[str, Any]] = {}

    for ev in events:
        created = ev.created_at or _utc_now()
        bucket = _time_bucket(created, bucket_hours)
        ip = ev.ip or "unknown"
        label = ev.threat_label or ev.source or "unknown"
        key = f"{ip}|{label}|{bucket}"

        if key not in clusters:
            clusters[key] = {
                "cluster_key": key,
                "ip": ip,
                "threat_label": label,
                "time_bucket": bucket,
                "representative_id": ev.id,
                "representative_status": ev.status,
                "max_score": ev.ai_score or 0,
                "total_count": 0,
                "event_ids": [],
            }

        c = clusters[key]
        c["total_count"] += 1
        c["event_ids"].append(ev.id)
        if (ev.ai_score or 0) > c["max_score"]:
            c["max_score"] = ev.ai_score or 0
            c["representative_id"] = ev.id

    result = sorted(clusters.values(), key=lambda x: x["total_count"], reverse=True)

    for c in result:
        if len(c["event_ids"]) > 50:
            c["event_ids"] = c["event_ids"][:50]

    return result


def get_cluster_detail(
    db: Session,
    cluster_key: str,
    hours: int = 24,
    bucket_hours: int = 1,
) -> Optional[Dict[str, Any]]:
    """获取指定聚类键的详情"""
    clusters = cluster_events(db, hours=hours, bucket_hours=bucket_hours)
    for c in clusters:
        if c["cluster_key"] == cluster_key:
            return c
    return None
