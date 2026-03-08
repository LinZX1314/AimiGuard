"""S4-04 AI性能基线与告警 测试"""
import time
import pytest


# ── AIPerformanceMonitor ──

def test_record_sample():
    """记录性能样本"""
    from services.ai_performance import AIPerformanceMonitor, PerformanceSample
    mon = AIPerformanceMonitor()
    sample = PerformanceSample(
        timestamp=time.time(), latency_ms=100, success=True, tokens_used=500
    )
    alerts = mon.record(sample)
    assert alerts == []  # 样本不足，不触发告警


def test_get_baseline():
    """计算性能基线"""
    from services.ai_performance import AIPerformanceMonitor, PerformanceSample
    mon = AIPerformanceMonitor()
    for i in range(20):
        mon.record(PerformanceSample(
            timestamp=time.time(), latency_ms=100 + i, success=True, tokens_used=500
        ))
    baseline = mon.get_baseline()
    assert baseline.sample_count == 20
    assert baseline.latency_mean > 0
    assert baseline.latency_std > 0
    assert baseline.success_rate == 1.0
    assert baseline.avg_tokens == 500


def test_latency_spike_alert():
    """延迟突增应触发告警"""
    from services.ai_performance import AIPerformanceMonitor, PerformanceSample
    mon = AIPerformanceMonitor()
    # 建立基线：100ms ± 小波动
    for i in range(30):
        mon.record(PerformanceSample(
            timestamp=time.time(), latency_ms=100 + (i % 5), success=True
        ))
    # 触发延迟异常
    alerts = mon.record(PerformanceSample(
        timestamp=time.time(), latency_ms=5000, success=True
    ))
    assert any(a.alert_type == "latency_spike" for a in alerts)


def test_high_error_rate_alert():
    """高错误率应触发告警"""
    from services.ai_performance import AIPerformanceMonitor, PerformanceSample
    mon = AIPerformanceMonitor()
    # 建立正常基线
    for i in range(15):
        mon.record(PerformanceSample(
            timestamp=time.time(), latency_ms=100, success=True
        ))
    # 连续失败
    for i in range(10):
        alerts = mon.record(PerformanceSample(
            timestamp=time.time(), latency_ms=100, success=False
        ))
    # 最后一次应触发错误率告警
    assert any(a.alert_type == "high_error_rate" for a in alerts)


def test_token_spike_alert():
    """Token用量突增应触发告警"""
    from services.ai_performance import AIPerformanceMonitor, PerformanceSample
    mon = AIPerformanceMonitor()
    for i in range(20):
        mon.record(PerformanceSample(
            timestamp=time.time(), latency_ms=100, success=True, tokens_used=500
        ))
    alerts = mon.record(PerformanceSample(
        timestamp=time.time(), latency_ms=100, success=True, tokens_used=5000
    ))
    assert any(a.alert_type == "token_spike" for a in alerts)


def test_no_alert_normal():
    """正常调用不应触发告警"""
    from services.ai_performance import AIPerformanceMonitor, PerformanceSample
    mon = AIPerformanceMonitor()
    for i in range(30):
        alerts = mon.record(PerformanceSample(
            timestamp=time.time(), latency_ms=100, success=True, tokens_used=500
        ))
    assert alerts == []


def test_get_alerts():
    """获取告警列表"""
    from services.ai_performance import AIPerformanceMonitor, PerformanceSample
    mon = AIPerformanceMonitor()
    for i in range(30):
        mon.record(PerformanceSample(
            timestamp=time.time(), latency_ms=100, success=True
        ))
    mon.record(PerformanceSample(
        timestamp=time.time(), latency_ms=10000, success=True
    ))
    alerts = mon.get_alerts()
    assert len(alerts) >= 1
    assert "alert_type" in alerts[0]


def test_clear_alerts():
    """清除告警"""
    from services.ai_performance import AIPerformanceMonitor, PerformanceSample
    mon = AIPerformanceMonitor()
    for i in range(30):
        mon.record(PerformanceSample(
            timestamp=time.time(), latency_ms=100, success=True
        ))
    mon.record(PerformanceSample(
        timestamp=time.time(), latency_ms=10000, success=True
    ))
    count = mon.clear_alerts()
    assert count >= 1
    assert mon.get_alerts() == []


def test_get_summary():
    """获取性能摘要"""
    from services.ai_performance import AIPerformanceMonitor, PerformanceSample
    mon = AIPerformanceMonitor()
    for i in range(10):
        mon.record(PerformanceSample(
            timestamp=time.time(), latency_ms=100, success=True, tokens_used=500
        ))
    summary = mon.get_summary()
    assert summary["sample_count"] == 10
    assert summary["latency_mean_ms"] > 0
    assert summary["success_rate"] == 1.0


def test_empty_baseline():
    """无数据时基线应全零"""
    from services.ai_performance import AIPerformanceMonitor
    mon = AIPerformanceMonitor()
    baseline = mon.get_baseline()
    assert baseline.sample_count == 0
    assert baseline.latency_mean == 0


# ── 快捷方法 ──

def test_record_ai_call():
    """快捷方法应正常工作"""
    from services.ai_performance import record_ai_call
    alerts = record_ai_call(latency_ms=100, success=True, tokens_used=500)
    assert isinstance(alerts, list)


def test_get_monitor_singleton():
    """全局单例"""
    from services.ai_performance import get_monitor
    m1 = get_monitor()
    m2 = get_monitor()
    assert m1 is m2
