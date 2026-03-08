"""
S4-04 AI 性能基线与告警
- 持续统计 AI 调用延迟、成功率、token 用量
- 建立性能基线（滑动窗口均值 + 标准差）
- 偏离基线时触发告警
"""
from __future__ import annotations

import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 基线配置
BASELINE_WINDOW_SIZE = 100       # 滑动窗口大小
LATENCY_ALERT_SIGMA = 3.0       # 延迟告警阈值 (3σ)
ERROR_RATE_THRESHOLD = 0.3      # 错误率告警阈值 30%
TOKEN_SPIKE_MULTIPLIER = 3.0    # Token 用量突增倍数


@dataclass
class PerformanceSample:
    """单次 AI 调用性能样本"""
    timestamp: float
    latency_ms: float
    success: bool
    tokens_used: int = 0
    model_name: str = ""
    context_type: str = ""


@dataclass
class PerformanceBaseline:
    """性能基线统计"""
    latency_mean: float = 0
    latency_std: float = 0
    success_rate: float = 1.0
    avg_tokens: float = 0
    sample_count: int = 0
    last_updated: Optional[str] = None


@dataclass
class PerformanceAlert:
    """性能告警"""
    alert_type: str
    level: str  # warning / critical
    message: str
    current_value: float
    baseline_value: float
    threshold: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AIPerformanceMonitor:
    """AI 性能监控器"""

    def __init__(self, window_size: int = BASELINE_WINDOW_SIZE):
        self._samples: deque[PerformanceSample] = deque(maxlen=window_size)
        self._alerts: List[PerformanceAlert] = []
        self._window_size = window_size

    def record(self, sample: PerformanceSample) -> List[PerformanceAlert]:
        """
        记录一次 AI 调用性能样本并检测异常。

        Returns:
            本次触发的告警列表
        """
        self._samples.append(sample)
        new_alerts = self._check_anomalies(sample)
        self._alerts.extend(new_alerts)
        return new_alerts

    def get_baseline(self) -> PerformanceBaseline:
        """计算当前性能基线"""
        if not self._samples:
            return PerformanceBaseline()

        latencies = [s.latency_ms for s in self._samples]
        successes = [s.success for s in self._samples]
        tokens = [s.tokens_used for s in self._samples]

        n = len(latencies)
        lat_mean = sum(latencies) / n
        lat_std = math.sqrt(sum((x - lat_mean) ** 2 for x in latencies) / max(n - 1, 1))
        success_rate = sum(1 for s in successes if s) / n
        avg_tokens = sum(tokens) / n if tokens else 0

        return PerformanceBaseline(
            latency_mean=round(lat_mean, 2),
            latency_std=round(lat_std, 2),
            success_rate=round(success_rate, 4),
            avg_tokens=round(avg_tokens, 2),
            sample_count=n,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

    def get_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近告警"""
        return [
            {
                "alert_type": a.alert_type,
                "level": a.level,
                "message": a.message,
                "current_value": a.current_value,
                "baseline_value": a.baseline_value,
                "threshold": a.threshold,
                "timestamp": a.timestamp,
            }
            for a in self._alerts[-limit:]
        ]

    def clear_alerts(self) -> int:
        """清除告警"""
        count = len(self._alerts)
        self._alerts.clear()
        return count

    def get_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        baseline = self.get_baseline()
        return {
            "sample_count": baseline.sample_count,
            "latency_mean_ms": baseline.latency_mean,
            "latency_std_ms": baseline.latency_std,
            "success_rate": baseline.success_rate,
            "avg_tokens": baseline.avg_tokens,
            "active_alerts": len(self._alerts),
            "last_updated": baseline.last_updated,
        }

    def _check_anomalies(self, sample: PerformanceSample) -> List[PerformanceAlert]:
        """检测性能异常"""
        alerts = []

        if len(self._samples) < 10:
            return alerts

        baseline = self.get_baseline()

        # 1. 延迟异常 (3σ)
        if baseline.latency_std > 0:
            upper_bound = baseline.latency_mean + LATENCY_ALERT_SIGMA * baseline.latency_std
            if sample.latency_ms > upper_bound:
                alerts.append(PerformanceAlert(
                    alert_type="latency_spike",
                    level="warning",
                    message=f"AI调用延迟异常: {sample.latency_ms:.0f}ms > 基线{baseline.latency_mean:.0f}±{baseline.latency_std:.0f}ms (3σ={upper_bound:.0f}ms)",
                    current_value=sample.latency_ms,
                    baseline_value=baseline.latency_mean,
                    threshold=upper_bound,
                ))

        # 2. 错误率异常
        recent = list(self._samples)[-20:]
        recent_errors = sum(1 for s in recent if not s.success)
        recent_error_rate = recent_errors / len(recent)
        if recent_error_rate > ERROR_RATE_THRESHOLD:
            alerts.append(PerformanceAlert(
                alert_type="high_error_rate",
                level="critical",
                message=f"AI调用错误率过高: {recent_error_rate:.1%} > 阈值{ERROR_RATE_THRESHOLD:.0%}",
                current_value=recent_error_rate,
                baseline_value=baseline.success_rate,
                threshold=ERROR_RATE_THRESHOLD,
            ))

        # 3. Token 用量突增
        if baseline.avg_tokens > 0 and sample.tokens_used > baseline.avg_tokens * TOKEN_SPIKE_MULTIPLIER:
            alerts.append(PerformanceAlert(
                alert_type="token_spike",
                level="warning",
                message=f"Token用量突增: {sample.tokens_used} > 基线{baseline.avg_tokens:.0f}×{TOKEN_SPIKE_MULTIPLIER:.0f}",
                current_value=sample.tokens_used,
                baseline_value=baseline.avg_tokens,
                threshold=baseline.avg_tokens * TOKEN_SPIKE_MULTIPLIER,
            ))

        return alerts


# 全局单例
_monitor = AIPerformanceMonitor()


def get_monitor() -> AIPerformanceMonitor:
    """获取全局性能监控器"""
    return _monitor


def record_ai_call(
    latency_ms: float,
    success: bool = True,
    tokens_used: int = 0,
    model_name: str = "",
    context_type: str = "",
) -> List[Dict[str, Any]]:
    """快捷方法：记录AI调用并返回触发的告警"""
    sample = PerformanceSample(
        timestamp=time.time(),
        latency_ms=latency_ms,
        success=success,
        tokens_used=tokens_used,
        model_name=model_name,
        context_type=context_type,
    )
    alerts = _monitor.record(sample)
    return [
        {
            "alert_type": a.alert_type,
            "level": a.level,
            "message": a.message,
        }
        for a in alerts
    ]
