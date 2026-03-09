"""MetricsCollector service tests — counters, latency stats, snapshot."""
from services.metrics_service import MetricsCollector


def _fresh():
    return MetricsCollector()


# ── Counters ──

def test_counter_default_zero():
    m = _fresh()
    assert m.get_counter("nonexistent") == 0


def test_counter_increment():
    m = _fresh()
    m.inc("requests")
    m.inc("requests")
    assert m.get_counter("requests") == 2


def test_counter_increment_delta():
    m = _fresh()
    m.inc("bytes", 1024)
    m.inc("bytes", 2048)
    assert m.get_counter("bytes") == 3072


def test_multiple_counters_independent():
    m = _fresh()
    m.inc("a", 5)
    m.inc("b", 10)
    assert m.get_counter("a") == 5
    assert m.get_counter("b") == 10


# ── Latency ──

def test_latency_empty():
    m = _fresh()
    stats = m.get_latency_stats("unknown")
    assert stats["count"] == 0
    assert stats["avg_ms"] == 0


def test_latency_single():
    m = _fresh()
    m.record_latency("api", 100.0)
    stats = m.get_latency_stats("api")
    assert stats["count"] == 1
    assert stats["avg_ms"] == 100.0
    assert stats["p50_ms"] == 100.0
    assert stats["max_ms"] == 100.0


def test_latency_multiple():
    m = _fresh()
    for v in [10, 20, 30, 40, 50]:
        m.record_latency("api", float(v))
    stats = m.get_latency_stats("api")
    assert stats["count"] == 5
    assert stats["avg_ms"] == 30.0
    assert stats["max_ms"] == 50.0


def test_latency_bucket_cap():
    m = _fresh()
    for i in range(600):
        m.record_latency("flood", float(i))
    stats = m.get_latency_stats("flood")
    # Bucket capped at 500
    assert stats["count"] == 500


def test_latency_p95():
    m = _fresh()
    for i in range(1, 101):
        m.record_latency("req", float(i))
    stats = m.get_latency_stats("req")
    # index = int(100 * 0.95) = 95 → value 96 (0-indexed in sorted [1..100])
    assert stats["p95_ms"] == 96.0


# ── Snapshot ──

def test_snapshot_structure():
    m = _fresh()
    m.inc("requests", 42)
    m.record_latency("api_request", 15.5)
    snap = m.snapshot()
    assert "uptime_seconds" in snap
    assert "boot_time" in snap
    assert "counters" in snap
    assert "latencies" in snap
    assert snap["counters"]["requests"] == 42
    assert snap["latencies"]["api_request"]["count"] == 1


def test_snapshot_boot_time_iso():
    m = _fresh()
    snap = m.snapshot()
    assert snap["boot_time"].endswith("Z")


def test_snapshot_uptime_positive():
    m = _fresh()
    snap = m.snapshot()
    assert snap["uptime_seconds"] >= 0
