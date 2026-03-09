"""WorkflowRelease tests — publish lock, release metadata, ISO formatting."""
from datetime import datetime, timezone
from threading import Lock

from services.workflow_release import (
    get_publish_lock,
    apply_release_metadata,
    _iso,
)


# ── _iso helper ──

def test_iso_none():
    assert _iso(None) is None


def test_iso_utc():
    dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    assert _iso(dt) == "2025-01-15T12:00:00Z"


def test_iso_naive_treated_as_utc():
    dt = datetime(2025, 6, 1, 8, 30, 0)
    result = _iso(dt)
    assert result.endswith("Z")
    assert "08:30:00" in result


# ── Publish lock ──

def test_get_publish_lock_returns_lock():
    lock = get_publish_lock(999)
    assert isinstance(lock, Lock)


def test_get_publish_lock_same_id_same_lock():
    lock1 = get_publish_lock(1000)
    lock2 = get_publish_lock(1000)
    assert lock1 is lock2


def test_get_publish_lock_different_ids():
    lock_a = get_publish_lock(2001)
    lock_b = get_publish_lock(2002)
    assert lock_a is not lock_b


# ── apply_release_metadata ──

def test_apply_release_metadata_basic():
    dsl = {"name": "test_wf", "metadata": {}}
    result = apply_release_metadata(
        dsl,
        canary_percent=20,
        effective_at=None,
        approval_reason="测试发布",
        actor="admin",
        trace_id="tr123",
    )
    release = result["metadata"]["release"]
    assert release["canary_percent"] == 20
    assert release["approval_reason"] == "测试发布"
    assert release["published_by"] == "admin"
    assert release["trace_id"] == "tr123"
    assert release["published_at"] is not None
    assert release["effective_at"] is None


def test_apply_release_metadata_with_effective_at():
    dt = datetime(2025, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    result = apply_release_metadata(
        {"name": "wf"},
        canary_percent=100,
        effective_at=dt,
        approval_reason="全量",
        actor="sys",
        trace_id=None,
    )
    assert result["metadata"]["release"]["effective_at"] == "2025-03-01T10:00:00Z"


def test_apply_release_metadata_no_existing_metadata():
    dsl = {"name": "wf"}
    result = apply_release_metadata(
        dsl,
        canary_percent=0,
        effective_at=None,
        approval_reason="r",
        actor="a",
        trace_id=None,
    )
    assert "release" in result["metadata"]


def test_apply_release_metadata_does_not_mutate_original():
    original = {"name": "wf", "metadata": {"existing": True}}
    result = apply_release_metadata(
        original,
        canary_percent=50,
        effective_at=None,
        approval_reason="r",
        actor="a",
        trace_id=None,
    )
    assert "release" not in original["metadata"]
    assert "release" in result["metadata"]
    assert result["metadata"]["existing"] is True
