"""
S4-03 异常 AI 行为告警
监控规则：
1. 连续 N 次 AI 评分全为满分/零分 → warning
2. AI 建议动作分布突变 → warning
3. AI 响应时延突增 > 3x 基线 → info
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from core.database import AIDecisionLog, ThreatEvent


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


CONSECUTIVE_THRESHOLD = 5
LATENCY_MULTIPLIER = 3.0
ACTION_SHIFT_THRESHOLD = 0.80


def check_consecutive_extreme_scores(
    db: Session,
    n: int = CONSECUTIVE_THRESHOLD,
) -> Optional[Dict[str, Any]]:
    """规则1: 最近 N 条威胁评分全为 0 或全为 100"""
    rows = (
        db.query(ThreatEvent.ai_score)
        .filter(ThreatEvent.ai_score.isnot(None))
        .order_by(ThreatEvent.created_at.desc())
        .limit(n)
        .all()
    )
    if len(rows) < n:
        return None

    scores = [r[0] for r in rows]
    if all(s == 100 for s in scores):
        return {
            "rule": "consecutive_extreme_scores",
            "level": "warning",
            "message": f"最近 {n} 条威胁评分全为满分(100)，AI 评分可能被操纵",
            "detail": {"scores": scores},
        }
    if all(s == 0 for s in scores):
        return {
            "rule": "consecutive_extreme_scores",
            "level": "warning",
            "message": f"最近 {n} 条威胁评分全为零分(0)，AI 评分可能被操纵",
            "detail": {"scores": scores},
        }
    return None


def check_action_distribution_shift(
    db: Session,
    window_hours: int = 24,
    threshold: float = ACTION_SHIFT_THRESHOLD,
) -> Optional[Dict[str, Any]]:
    """规则2: 最近时间窗口内某一动作建议占比超过阈值"""
    since = _utc_now() - timedelta(hours=window_hours)
    rows = (
        db.query(
            ThreatEvent.action_suggest,
            func.count(ThreatEvent.id).label("cnt"),
        )
        .filter(
            ThreatEvent.created_at >= since,
            ThreatEvent.action_suggest.isnot(None),
        )
        .group_by(ThreatEvent.action_suggest)
        .all()
    )
    if not rows:
        return None

    total = sum(r.cnt for r in rows)
    if total < 5:
        return None

    for r in rows:
        ratio = r.cnt / total
        if ratio >= threshold:
            return {
                "rule": "action_distribution_shift",
                "level": "warning",
                "message": f"近 {window_hours}h 内 {r.action_suggest} 建议占比 {ratio:.0%}（阈值 {threshold:.0%}），AI 建议分布可能异常",
                "detail": {
                    "action": r.action_suggest,
                    "count": r.cnt,
                    "total": total,
                    "ratio": round(ratio, 3),
                },
            }
    return None


def check_latency_spike(
    db: Session,
    multiplier: float = LATENCY_MULTIPLIER,
    baseline_hours: int = 168,
    recent_hours: int = 1,
) -> Optional[Dict[str, Any]]:
    """规则3: 最近 1h 平均推理时延 > 基线时延 * multiplier"""
    now = _utc_now()
    baseline_since = now - timedelta(hours=baseline_hours)
    recent_since = now - timedelta(hours=recent_hours)

    baseline_avg = (
        db.query(func.avg(AIDecisionLog.inference_ms))
        .filter(
            AIDecisionLog.created_at >= baseline_since,
            AIDecisionLog.inference_ms.isnot(None),
        )
        .scalar()
    )
    if baseline_avg is None or baseline_avg <= 0:
        return None

    recent_avg = (
        db.query(func.avg(AIDecisionLog.inference_ms))
        .filter(
            AIDecisionLog.created_at >= recent_since,
            AIDecisionLog.inference_ms.isnot(None),
        )
        .scalar()
    )
    if recent_avg is None:
        return None

    if recent_avg > baseline_avg * multiplier:
        return {
            "rule": "latency_spike",
            "level": "info",
            "message": f"近 {recent_hours}h 平均推理时延 {recent_avg:.0f}ms，超过基线 {baseline_avg:.0f}ms 的 {multiplier}x，可能被注入复杂 Prompt",
            "detail": {
                "baseline_avg_ms": round(baseline_avg, 2),
                "recent_avg_ms": round(recent_avg, 2),
                "multiplier": multiplier,
            },
        }
    return None


def run_all_checks(db: Session) -> List[Dict[str, Any]]:
    """执行所有异常检测规则，返回告警列表"""
    alerts: List[Dict[str, Any]] = []

    result = check_consecutive_extreme_scores(db)
    if result:
        alerts.append(result)

    result = check_action_distribution_shift(db)
    if result:
        alerts.append(result)

    result = check_latency_spike(db)
    if result:
        alerts.append(result)

    return alerts
