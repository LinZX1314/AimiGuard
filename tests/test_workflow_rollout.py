"""WorkflowRollout tests — normalize, routing, snapshot, DB persistence."""
import pytest
from datetime import datetime, timezone

from core.database import SessionLocal, SystemConfigSnapshot
from services.workflow_rollout import (
    _normalize_mode,
    _normalize_gray_percent,
    _snapshot_payload,
    get_defense_workflow_rollout,
    set_defense_workflow_rollout,
    should_route_to_workflow_runtime,
    DEFENSE_WORKFLOW_ROLLOUT_KEY,
    DEFAULT_DEFENSE_WORKFLOW_ROLLOUT,
)


# ── _normalize_mode ──

def test_normalize_mode_valid():
    assert _normalize_mode("legacy_only") == "legacy_only"
    assert _normalize_mode("workflow_gray") == "workflow_gray"
    assert _normalize_mode("workflow_full") == "workflow_full"


def test_normalize_mode_invalid():
    assert _normalize_mode("bad") == "legacy_only"
    assert _normalize_mode(None) == "legacy_only"
    assert _normalize_mode("") == "legacy_only"


# ── _normalize_gray_percent ──

def test_normalize_gray_percent_valid():
    assert _normalize_gray_percent(50) == 50


def test_normalize_gray_percent_clamped():
    assert _normalize_gray_percent(-10) == 0
    assert _normalize_gray_percent(200) == 100


def test_normalize_gray_percent_invalid():
    assert _normalize_gray_percent("abc") == 0
    assert _normalize_gray_percent(None) == 0


# ── _snapshot_payload ──

def test_snapshot_payload_none():
    result = _snapshot_payload(None)
    assert result["mode"] == "legacy_only"
    assert result["gray_percent"] == 0


def test_snapshot_payload_malformed_json():
    class FakeRow:
        def __getitem__(self, idx):
            if idx == 0:
                return "not_json{{"
            return None
    result = _snapshot_payload(FakeRow())
    assert result["mode"] == "legacy_only"


# ── should_route_to_workflow_runtime ──

def test_route_legacy_only():
    assert should_route_to_workflow_runtime(
        rollout={"mode": "legacy_only"}, routing_key="k1",
    ) is False


def test_route_workflow_full():
    assert should_route_to_workflow_runtime(
        rollout={"mode": "workflow_full"}, routing_key="k1",
    ) is True


def test_route_gray_zero():
    assert should_route_to_workflow_runtime(
        rollout={"mode": "workflow_gray", "gray_percent": 0}, routing_key="k1",
    ) is False


def test_route_gray_100():
    assert should_route_to_workflow_runtime(
        rollout={"mode": "workflow_gray", "gray_percent": 100}, routing_key="k1",
    ) is True


def test_route_gray_deterministic():
    rollout = {"mode": "workflow_gray", "gray_percent": 50}
    result1 = should_route_to_workflow_runtime(rollout=rollout, routing_key="test_key_1")
    result2 = should_route_to_workflow_runtime(rollout=rollout, routing_key="test_key_1")
    assert result1 == result2  # Same key → same result


# ── DB integration ──

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_get_default_rollout(db):
    result = get_defense_workflow_rollout(db, "test_env_rollout")
    assert result["mode"] == "legacy_only"


def test_set_and_get_rollout(db):
    set_defense_workflow_rollout(
        db,
        mode="workflow_gray",
        gray_percent=30,
        double_write_metrics=True,
        reason="灰度发布",
        operator="admin",
        env="test_env_rollout_set",
        trace_id="tr1",
    )
    result = get_defense_workflow_rollout(db, "test_env_rollout_set")
    assert result["mode"] == "workflow_gray"
    assert result["gray_percent"] == 30
    assert result["double_write_metrics"] is True
