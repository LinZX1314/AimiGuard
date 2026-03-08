"""D3 误报标记与反馈闭环 + 误报率统计 测试"""
import uuid
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session as SASession
from sqlalchemy import text


def _seed_event(db: SASession, ip: str = "10.0.0.1", status: str = "PENDING") -> int:
    """插入一条 threat_event 并返回 id"""
    trace_id = str(uuid.uuid4())
    db.execute(
        text(
            """
            INSERT INTO threat_event (ip, source, status, trace_id, created_at, updated_at)
            VALUES (:ip, 'test', :status, :trace_id, datetime('now'), datetime('now'))
            """
        ),
        {"ip": ip, "status": status, "trace_id": trace_id},
    )
    row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
    eid = row[0]
    db.commit()
    return eid


# ── D3-01 误报标记 ──

def test_mark_false_positive(client: TestClient, admin_token: str, db: SASession):
    """标记事件为误报应更新状态和字段"""
    eid = _seed_event(db, ip="192.168.1.100")
    res = client.post(
        f"/api/v1/defense/events/{eid}/false-positive",
        json={"reason": "经核实为内部扫描"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["code"] == 0

    row = db.execute(
        text("SELECT status, false_positive_by, false_positive_reason FROM threat_event WHERE id = :id"),
        {"id": eid},
    ).fetchone()
    assert row[0] == "FALSE_POSITIVE"
    assert row[1] == "admin"
    assert row[2] == "经核实为内部扫描"


def test_mark_false_positive_not_found(client: TestClient, admin_token: str):
    """标记不存在的事件应返回 404"""
    res = client.post(
        "/api/v1/defense/events/99999/false-positive",
        json={"reason": "test"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 404


def test_mark_false_positive_with_reason(client: TestClient, admin_token: str, db: SASession):
    """标记误报时可附带原因说明"""
    eid = _seed_event(db, ip="10.0.0.5")
    res = client.post(
        f"/api/v1/defense/events/{eid}/false-positive",
        json={"reason": ""},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    row = db.execute(
        text("SELECT status, false_positive_reason FROM threat_event WHERE id = :id"),
        {"id": eid},
    ).fetchone()
    assert row[0] == "FALSE_POSITIVE"
    assert row[1] is None  # empty reason stored as None


# ── D3-02 误报率统计 ──

def test_false_positive_stats_empty(client: TestClient, admin_token: str):
    """无事件时误报率应为 0"""
    res = client.get(
        "/api/v1/overview/false-positive-stats?range=7d",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["false_positive_rate"] == 0.0
    assert data["false_positive_count"] == 0


def test_false_positive_stats_with_data(client: TestClient, admin_token: str, db: SASession):
    """有误报事件时应正确计算误报率"""
    for i in range(4):
        _seed_event(db, ip=f"10.0.0.{i}", status="PENDING")
    fp_id = _seed_event(db, ip="10.0.0.99", status="FALSE_POSITIVE")

    res = client.get(
        "/api/v1/overview/false-positive-stats?range=7d",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total_events"] == 5
    assert data["false_positive_count"] == 1
    assert data["false_positive_rate"] == 20.0
    assert data["over_threshold"] is False
