"""S4-02 AI 自主动作边界控制 测试"""
import uuid
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session as SASession
from sqlalchemy import text


def _seed_event(db: SASession, ip: str = "10.0.0.1") -> int:
    trace_id = str(uuid.uuid4())
    db.execute(
        text(
            "INSERT INTO threat_event (ip, source, status, trace_id, created_at, updated_at) "
            "VALUES (:ip, 'test', 'PENDING', :trace_id, datetime('now'), datetime('now'))"
        ),
        {"ip": ip, "trace_id": trace_id},
    )
    row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
    eid = row[0]
    db.commit()
    return eid


# ── action_suggest 白名单 ──

def test_normalize_action_allowed():
    """_normalize_action 仅允许 BLOCK/MONITOR/IGNORE"""
    from services.ai_engine import _normalize_action, ALLOWED_ACTIONS

    assert ALLOWED_ACTIONS == {"BLOCK", "MONITOR", "IGNORE"}
    assert _normalize_action("BLOCK", 90) == "BLOCK"
    assert _normalize_action("MONITOR", 50) == "MONITOR"
    assert _normalize_action("IGNORE", 10) == "IGNORE"


def test_normalize_action_rejects_invalid():
    """_normalize_action 拒绝非白名单值，按 score 降级"""
    from services.ai_engine import _normalize_action

    assert _normalize_action("EXECUTE_SHELL", 90) == "BLOCK"
    assert _normalize_action("rm -rf /", 30) == "MONITOR"
    assert _normalize_action("", 50) == "MONITOR"
    assert _normalize_action(None, 85) == "BLOCK"


# ── approved_by 校验 ──

def test_approve_event_sets_approved_by(client: TestClient, admin_token: str, db: SASession):
    """批准事件应自动设置 approved_by"""
    eid = _seed_event(db, ip="10.10.10.1")
    res = client.post(
        f"/api/v1/defense/events/{eid}/approve",
        json={"reason": "测试审批"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200

    row = db.execute(
        text("SELECT approved_by FROM execution_task WHERE event_id = :eid ORDER BY id DESC LIMIT 1"),
        {"eid": eid},
    ).fetchone()
    assert row is not None
    assert row[0] == "admin"


def test_execution_task_without_approved_by_rejected(db: SASession):
    """没有 approved_by 的执行任务应被拒绝执行"""
    import asyncio
    from api.defense import _run_execution_task_background

    eid = _seed_event(db, ip="10.10.10.2")
    trace_id = str(uuid.uuid4())

    db.execute(
        text(
            "INSERT INTO execution_task (event_id, action, state, trace_id, created_at, updated_at) "
            "VALUES (:eid, 'BLOCK', 'QUEUED', :tid, datetime('now'), datetime('now'))"
        ),
        {"eid": eid, "tid": trace_id},
    )
    row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
    task_id = row[0]
    db.commit()

    from tests.conftest import TestingSessionLocal
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(
            _run_execution_task_background(task_id, trace_id, "test", TestingSessionLocal)
        )
    finally:
        loop.close()

    fresh = TestingSessionLocal()
    try:
        row = fresh.execute(
            text("SELECT state, error_message FROM execution_task WHERE id = :tid"),
            {"tid": task_id},
        ).fetchone()
        assert row[0] == "MANUAL_REQUIRED"
        assert "approved_by" in row[1]
    finally:
        fresh.close()
