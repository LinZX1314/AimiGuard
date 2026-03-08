"""D1-01 CVE数据库集成与自动关联 测试"""
import uuid
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session as SASession
from sqlalchemy import text


def _seed_finding_with_cve(db: SASession, cve: str = "CVE-2024-0001") -> int:
    """创建 asset + scan_task + finding 并返回 finding_id"""
    tid = str(uuid.uuid4())
    db.execute(
        text(
            "INSERT INTO asset (target, target_type, created_at, updated_at) "
            "VALUES ('10.0.0.1', 'IP', datetime('now'), datetime('now'))"
        )
    )
    row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
    asset_id = row[0]
    db.execute(
        text(
            "INSERT INTO scan_task (asset_id, target, target_type, tool_name, state, trace_id, created_at, updated_at) "
            "VALUES (:aid, '10.0.0.1', 'IP', 'nmap', 'SUCCESS', :tid, datetime('now'), datetime('now'))"
        ),
        {"aid": asset_id, "tid": tid},
    )
    row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
    task_id = row[0]
    ftid = str(uuid.uuid4())
    db.execute(
        text(
            "INSERT INTO scan_finding (scan_task_id, asset, port, service, vuln_id, cve, severity, status, trace_id, created_at, updated_at) "
            "VALUES (:task_id, '10.0.0.1', 22, 'ssh', :cve, :cve, 'HIGH', 'NEW', :tid, datetime('now'), datetime('now'))"
        ),
        {"task_id": task_id, "cve": cve, "tid": ftid},
    )
    row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
    fid = row[0]
    db.commit()
    return fid


# ── threat_intel 服务逻辑 ──

def test_enrich_cve_fallback():
    """NVD不可达时应降级返回"""
    import asyncio
    from services.threat_intel import enrich_cve

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(enrich_cve("CVE-9999-99999"))
    finally:
        loop.close()

    assert isinstance(result, dict)
    assert "cvss_score" in result
    assert "degraded" in result


def test_enrich_empty_cve():
    """空CVE应降级"""
    import asyncio
    from services.threat_intel import enrich_cve

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(enrich_cve(""))
    finally:
        loop.close()

    assert result["degraded"] is True
    assert result["fallback_reason"] == "empty_cve_id"


def test_cache_works():
    """缓存应生效，重复查询不再请求"""
    import asyncio
    from services.threat_intel import enrich_cve, clear_cache

    clear_cache()
    loop = asyncio.new_event_loop()
    try:
        r1 = loop.run_until_complete(enrich_cve("CVE-2024-TEST-CACHE"))
        r2 = loop.run_until_complete(enrich_cve("CVE-2024-TEST-CACHE"))
    finally:
        loop.close()

    assert r2.get("from_cache") is True


def test_clear_cache():
    """清除缓存应成功"""
    from services.threat_intel import clear_cache, _cve_cache
    _cve_cache["test"] = {"data": {}, "ts": 0}
    count = clear_cache()
    assert count >= 1


# ── API 端点 ──

def test_enrich_finding_api(client: TestClient, admin_token: str, db: SASession):
    """POST /scan/findings/{id}/enrich 应触发CVE补充"""
    fid = _seed_finding_with_cve(db)

    res = client.post(
        f"/api/v1/scan/findings/{fid}/enrich",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["finding_id"] == fid
    assert "cvss_score" in data
    assert "cve_id" in data


def test_enrich_finding_no_cve(client: TestClient, admin_token: str, db: SASession):
    """无CVE的finding应返回400"""
    tid = str(uuid.uuid4())
    db.execute(
        text(
            "INSERT INTO asset (target, target_type, created_at, updated_at) "
            "VALUES ('10.0.0.2', 'IP', datetime('now'), datetime('now'))"
        )
    )
    row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
    asset_id = row[0]
    db.execute(
        text(
            "INSERT INTO scan_task (asset_id, target, target_type, tool_name, state, trace_id, created_at, updated_at) "
            "VALUES (:aid, '10.0.0.2', 'IP', 'nmap', 'SUCCESS', :tid, datetime('now'), datetime('now'))"
        ),
        {"aid": asset_id, "tid": tid},
    )
    row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
    task_id = row[0]
    ftid = str(uuid.uuid4())
    db.execute(
        text(
            "INSERT INTO scan_finding (scan_task_id, asset, severity, status, trace_id, created_at, updated_at) "
            "VALUES (:task_id, '10.0.0.2', 'LOW', 'NEW', :tid, datetime('now'), datetime('now'))"
        ),
        {"task_id": task_id, "tid": ftid},
    )
    row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
    fid = row[0]
    db.commit()

    res = client.post(
        f"/api/v1/scan/findings/{fid}/enrich",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 400


def test_enrich_finding_not_found(client: TestClient, admin_token: str):
    """不存在的finding应404"""
    res = client.post(
        "/api/v1/scan/findings/99999/enrich",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 404
