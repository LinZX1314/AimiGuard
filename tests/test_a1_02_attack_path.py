"""A1-02 攻击路径可视化（横向移动分析）测试"""
import uuid
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session as SASession
from sqlalchemy import text


def _seed_task_with_findings(db: SASession, findings_data: list) -> int:
    """创建 asset + scan_task + findings，返回 task_id"""
    tid = str(uuid.uuid4())
    db.execute(
        text(
            "INSERT INTO asset (target, target_type, created_at, updated_at) "
            "VALUES ('10.0.0.0/24', 'CIDR', datetime('now'), datetime('now'))"
        )
    )
    row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
    asset_id = row[0]
    db.execute(
        text(
            "INSERT INTO scan_task (asset_id, target, target_type, tool_name, state, trace_id, created_at, updated_at) "
            "VALUES (:aid, '10.0.0.0/24', 'CIDR', 'nmap', 'SUCCESS', :tid, datetime('now'), datetime('now'))"
        ),
        {"aid": asset_id, "tid": tid},
    )
    row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
    task_id = row[0]

    for f in findings_data:
        ftid = str(uuid.uuid4())
        db.execute(
            text(
                "INSERT INTO scan_finding (scan_task_id, asset, port, service, severity, status, trace_id, created_at, updated_at) "
                "VALUES (:task_id, :asset, :port, :service, :severity, 'NEW', :tid, datetime('now'), datetime('now'))"
            ),
            {"task_id": task_id, "asset": f["asset"], "port": f["port"], "service": f["service"], "severity": f["severity"], "tid": ftid},
        )
    db.commit()
    return task_id


# ── analyze_attack_path 逻辑测试 ──

def test_attack_path_lateral_movement():
    """两台主机都有SSH应产生横向移动边"""
    import asyncio
    from services.ai_engine import ai_engine

    assets = [{"ip": "10.0.0.1"}, {"ip": "10.0.0.2"}]
    findings = [
        {"asset": "10.0.0.1", "port": 22, "service": "ssh", "severity": "HIGH"},
        {"asset": "10.0.0.2", "port": 22, "service": "ssh", "severity": "HIGH"},
    ]

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(ai_engine.analyze_attack_path(assets, findings))
    finally:
        loop.close()

    assert result["total_nodes"] == 2
    assert result["high_risk_count"] == 2
    assert result["total_edges"] >= 1
    assert any("ssh" in e["label"] for e in result["edges"])


def test_attack_path_no_lateral():
    """无高危服务共享时不应产生边"""
    import asyncio
    from services.ai_engine import ai_engine

    assets = [{"ip": "10.0.0.1"}, {"ip": "10.0.0.2"}]
    findings = [
        {"asset": "10.0.0.1", "port": 80, "service": "http", "severity": "LOW"},
        {"asset": "10.0.0.2", "port": 443, "service": "https", "severity": "LOW"},
    ]

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(ai_engine.analyze_attack_path(assets, findings))
    finally:
        loop.close()

    assert result["total_edges"] == 0
    assert result["high_risk_count"] == 0


def test_attack_path_empty():
    """无资产时应返回空图"""
    import asyncio
    from services.ai_engine import ai_engine

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(ai_engine.analyze_attack_path([], []))
    finally:
        loop.close()

    assert result["total_nodes"] == 0
    assert result["total_edges"] == 0


# ── API 端点测试 ──

def test_attack_path_api(client: TestClient, admin_token: str, db: SASession):
    """GET /scan/tasks/{id}/attack-path 应返回攻击路径图"""
    task_id = _seed_task_with_findings(db, [
        {"asset": "10.0.0.1", "port": 22, "service": "ssh", "severity": "HIGH"},
        {"asset": "10.0.0.2", "port": 22, "service": "ssh", "severity": "HIGH"},
        {"asset": "10.0.0.1", "port": 445, "service": "smb", "severity": "CRITICAL"},
    ])

    res = client.get(
        f"/api/v1/scan/tasks/{task_id}/attack-path",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert "nodes" in data
    assert "edges" in data
    assert data["total_nodes"] >= 2
    assert data["high_risk_count"] >= 1


def test_attack_path_api_not_found(client: TestClient, admin_token: str):
    """不存在的任务应 404"""
    res = client.get(
        "/api/v1/scan/tasks/99999/attack-path",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 404
