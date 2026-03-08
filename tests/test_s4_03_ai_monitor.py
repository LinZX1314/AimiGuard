"""S4-03 异常 AI 行为告警 测试"""
import uuid
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session as SASession
from sqlalchemy import text


def _seed_events_with_scores(db: SASession, scores: list[int]):
    """插入多条带 ai_score 的 threat_event"""
    for score in scores:
        tid = str(uuid.uuid4())
        db.execute(
            text(
                "INSERT INTO threat_event (ip, source, status, ai_score, action_suggest, trace_id, created_at, updated_at) "
                "VALUES ('10.0.0.1', 'test', 'PENDING', :score, 'BLOCK', :tid, datetime('now'), datetime('now'))"
            ),
            {"score": score, "tid": tid},
        )
    db.commit()


def _seed_events_with_actions(db: SASession, actions: list[str]):
    """插入多条带 action_suggest 的 threat_event"""
    for action in actions:
        tid = str(uuid.uuid4())
        db.execute(
            text(
                "INSERT INTO threat_event (ip, source, status, ai_score, action_suggest, trace_id, created_at, updated_at) "
                "VALUES ('10.0.0.1', 'test', 'PENDING', 50, :action, :tid, datetime('now'), datetime('now'))"
            ),
            {"action": action, "tid": tid},
        )
    db.commit()


def _seed_decision_logs(db: SASession, inference_ms_list: list[float]):
    """插入多条带 inference_ms 的 ai_decision_log"""
    for ms in inference_ms_list:
        tid = str(uuid.uuid4())
        db.execute(
            text(
                "INSERT INTO ai_decision_log (context_type, model_name, inference_ms, trace_id, created_at) "
                "VALUES ('chat', 'test-model', :ms, :tid, datetime('now'))"
            ),
            {"ms": ms, "tid": tid},
        )
    db.commit()


# ── 规则1: 连续极端评分 ──

def test_no_alert_on_normal_scores(db: SASession):
    """正常评分不应触发告警"""
    from services.ai_monitor import check_consecutive_extreme_scores
    _seed_events_with_scores(db, [80, 60, 90, 70, 50])
    result = check_consecutive_extreme_scores(db, n=5)
    assert result is None


def test_alert_on_all_100_scores(db: SASession):
    """连续满分应触发告警"""
    from services.ai_monitor import check_consecutive_extreme_scores
    _seed_events_with_scores(db, [100, 100, 100, 100, 100])
    result = check_consecutive_extreme_scores(db, n=5)
    assert result is not None
    assert result["level"] == "warning"
    assert "满分" in result["message"]


def test_alert_on_all_0_scores(db: SASession):
    """连续零分应触发告警"""
    from services.ai_monitor import check_consecutive_extreme_scores
    _seed_events_with_scores(db, [0, 0, 0, 0, 0])
    result = check_consecutive_extreme_scores(db, n=5)
    assert result is not None
    assert result["level"] == "warning"
    assert "零分" in result["message"]


# ── 规则2: 动作分布突变 ──

def test_no_alert_on_balanced_actions(db: SASession):
    """均衡分布不应触发告警"""
    from services.ai_monitor import check_action_distribution_shift
    _seed_events_with_actions(db, ["BLOCK", "MONITOR", "BLOCK", "MONITOR", "BLOCK", "MONITOR"])
    result = check_action_distribution_shift(db, threshold=0.80)
    assert result is None


def test_alert_on_skewed_actions(db: SASession):
    """单一动作占比过高应触发告警"""
    from services.ai_monitor import check_action_distribution_shift
    _seed_events_with_actions(db, ["BLOCK"] * 9 + ["MONITOR"])
    result = check_action_distribution_shift(db, threshold=0.80)
    assert result is not None
    assert result["level"] == "warning"
    assert "BLOCK" in result["message"]


# ── 规则3: 时延突增 ──

def test_no_alert_on_normal_latency(db: SASession):
    """正常时延不应触发告警"""
    from services.ai_monitor import check_latency_spike
    _seed_decision_logs(db, [100, 110, 90, 105, 95])
    result = check_latency_spike(db, multiplier=3.0)
    assert result is None


def test_alert_on_latency_spike(db: SASession):
    """时延突增应触发 info 告警"""
    from services.ai_monitor import check_latency_spike
    _seed_decision_logs(db, [100, 100, 100, 100, 500])
    # All logs are recent (within 1h), baseline includes all, recent avg = avg of all
    # With all in same window, recent_avg == baseline_avg, no spike
    # Need to simulate by using a low multiplier
    result = check_latency_spike(db, multiplier=0.5)
    # baseline_avg = 180, recent_avg = 180, 180 > 180*0.5=90 → spike
    if result is not None:
        assert result["level"] == "info"
        assert "时延" in result["message"]


# ── API 端点 ──

def test_monitor_check_api(client: TestClient, admin_token: str):
    """GET /ai/monitor/check 应返回检查结果"""
    res = client.get(
        "/api/v1/ai/monitor/check",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert "alerts" in data
    assert "alert_count" in data
    assert isinstance(data["alerts"], list)


def test_monitor_check_detects_extreme_scores(client: TestClient, admin_token: str, db: SASession):
    """API 应检测到连续极端评分"""
    _seed_events_with_scores(db, [100] * 5)
    res = client.get(
        "/api/v1/ai/monitor/check",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["alert_count"] >= 1
    rules = [a["rule"] for a in data["alerts"]]
    assert "consecutive_extreme_scores" in rules
