"""
可观测性核心指标采集服务。
在内存中累计关键指标，供 /api/v1/system/metrics 读取。
"""
import time
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from typing import Optional


class MetricsCollector:
    """线程安全的指标收集器"""

    def __init__(self):
        self._lock = Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._latencies: dict[str, list[float]] = defaultdict(list)
        self._started_at = time.monotonic()
        self._boot_time = datetime.now(timezone.utc)

    # ── 计数器 ──

    def inc(self, name: str, delta: int = 1):
        with self._lock:
            self._counters[name] += delta

    def get_counter(self, name: str) -> int:
        with self._lock:
            return self._counters.get(name, 0)

    # ── 延迟记录 ──

    def record_latency(self, name: str, ms: float):
        with self._lock:
            bucket = self._latencies[name]
            bucket.append(ms)
            if len(bucket) > 500:
                self._latencies[name] = bucket[-500:]

    def get_latency_stats(self, name: str) -> dict:
        with self._lock:
            bucket = list(self._latencies.get(name, []))
        if not bucket:
            return {"count": 0, "avg_ms": 0, "p50_ms": 0, "p95_ms": 0, "max_ms": 0}
        bucket.sort()
        n = len(bucket)
        return {
            "count": n,
            "avg_ms": round(sum(bucket) / n, 2),
            "p50_ms": round(bucket[n // 2], 2),
            "p95_ms": round(bucket[int(n * 0.95)], 2),
            "max_ms": round(bucket[-1], 2),
        }

    # ── 快照 ──

    def snapshot(self) -> dict:
        with self._lock:
            counters = dict(self._counters)
        latency_names = ["api_request", "ai_chat", "firewall_sync", "scan_dispatch"]
        latencies = {name: self.get_latency_stats(name) for name in latency_names}

        uptime_s = time.monotonic() - self._started_at
        return {
            "uptime_seconds": round(uptime_s, 1),
            "boot_time": self._boot_time.isoformat().replace("+00:00", "Z"),
            "counters": counters,
            "latencies": latencies,
        }


# 全局单例
metrics = MetricsCollector()
