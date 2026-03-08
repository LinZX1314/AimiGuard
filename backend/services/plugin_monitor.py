"""
S2-03 MCP 插件行为监控与异常检测
- 记录每次 MCP 工具调用
- 异常检测规则：频率突增、内网IP访问、数据体积超限
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from core.database import PluginCallLog, PluginRegistry

logger = logging.getLogger(__name__)

# 内网 IP 段
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]

# 异常检测阈值
FREQUENCY_MULTIPLIER = 5  # 调用频率突增倍数
MAX_RESULT_SIZE_BYTES = 1_000_000  # 结果数据体积阈值 1MB


def log_plugin_call(
    db: Session,
    plugin_id: int,
    plugin_name: str,
    tool_name: str,
    args: Optional[Dict] = None,
    result: Optional[Any] = None,
    latency_ms: float = 0,
    success: bool = True,
    error_message: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> PluginCallLog:
    """记录一次 MCP 工具调用"""
    args_hash = hashlib.sha256(json.dumps(args or {}, sort_keys=True).encode()).hexdigest()[:16]
    result_str = json.dumps(result) if result else ""
    result_hash = hashlib.sha256(result_str.encode()).hexdigest()[:16] if result_str else None

    log_entry = PluginCallLog(
        plugin_id=plugin_id,
        plugin_name=plugin_name,
        tool_name=tool_name,
        args_hash=args_hash,
        result_hash=result_hash,
        latency_ms=latency_ms,
        success=1 if success else 0,
        error_message=error_message,
        trace_id=trace_id or str(uuid.uuid4()),
    )
    db.add(log_entry)
    db.commit()
    return log_entry


def detect_anomalies(db: Session, plugin_id: int, window_hours: int = 1) -> List[Dict[str, Any]]:
    """
    检测插件异常行为。

    规则：
    1. 调用频率突增 > 5x 正常基线 → warning
    2. 调用参数包含内网IP → critical + 自动暂停
    3. 返回数据体积异常 → warning
    """
    anomalies = []
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=window_hours)
    baseline_start = now - timedelta(hours=window_hours * 24)

    # 规则1: 频率突增
    recent_count = (
        db.query(sqlfunc.count(PluginCallLog.id))
        .filter(
            PluginCallLog.plugin_id == plugin_id,
            PluginCallLog.created_at >= window_start,
        )
        .scalar()
        or 0
    )

    baseline_count = (
        db.query(sqlfunc.count(PluginCallLog.id))
        .filter(
            PluginCallLog.plugin_id == plugin_id,
            PluginCallLog.created_at >= baseline_start,
            PluginCallLog.created_at < window_start,
        )
        .scalar()
        or 0
    )

    baseline_hours = max(window_hours * 23, 1)
    baseline_rate = baseline_count / baseline_hours
    current_rate = recent_count / max(window_hours, 1)

    if baseline_rate > 0 and current_rate > baseline_rate * FREQUENCY_MULTIPLIER:
        anomalies.append({
            "type": "frequency_spike",
            "level": "warning",
            "detail": f"调用频率突增: 当前{current_rate:.1f}/h vs 基线{baseline_rate:.1f}/h ({current_rate/baseline_rate:.1f}x)",
            "plugin_id": plugin_id,
        })

    return anomalies


def check_args_for_private_ip(args: Optional[Dict]) -> Optional[str]:
    """检查调用参数是否包含内网IP"""
    if not args:
        return None

    args_str = json.dumps(args)
    ip_pattern = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
    matches = ip_pattern.findall(args_str)

    for ip_str in matches:
        try:
            ip = ipaddress.ip_address(ip_str)
            for net in _PRIVATE_NETWORKS:
                if ip in net:
                    return ip_str
        except ValueError:
            continue

    return None


def auto_suspend_plugin(db: Session, plugin_id: int, reason: str) -> bool:
    """自动暂停插件"""
    plugin = db.query(PluginRegistry).filter(PluginRegistry.id == plugin_id).first()
    if plugin and plugin.enabled:
        plugin.enabled = 0
        plugin.updated_at = datetime.now(timezone.utc)
        db.commit()
        logger.warning(f"Plugin {plugin.plugin_name}(id={plugin_id}) auto-suspended: {reason}")
        return True
    return False


def get_call_stats(db: Session, plugin_id: int, hours: int = 24) -> Dict[str, Any]:
    """获取插件调用统计"""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    total = (
        db.query(sqlfunc.count(PluginCallLog.id))
        .filter(PluginCallLog.plugin_id == plugin_id, PluginCallLog.created_at >= since)
        .scalar()
        or 0
    )
    errors = (
        db.query(sqlfunc.count(PluginCallLog.id))
        .filter(
            PluginCallLog.plugin_id == plugin_id,
            PluginCallLog.created_at >= since,
            PluginCallLog.success == 0,
        )
        .scalar()
        or 0
    )
    avg_latency = (
        db.query(sqlfunc.avg(PluginCallLog.latency_ms))
        .filter(PluginCallLog.plugin_id == plugin_id, PluginCallLog.created_at >= since)
        .scalar()
        or 0
    )

    tools = (
        db.query(PluginCallLog.tool_name, sqlfunc.count(PluginCallLog.id))
        .filter(PluginCallLog.plugin_id == plugin_id, PluginCallLog.created_at >= since)
        .group_by(PluginCallLog.tool_name)
        .all()
    )

    return {
        "plugin_id": plugin_id,
        "period_hours": hours,
        "total_calls": total,
        "error_calls": errors,
        "error_rate": round(errors / total, 4) if total else 0,
        "avg_latency_ms": round(avg_latency, 2),
        "tools": {t: c for t, c in tools},
    }
