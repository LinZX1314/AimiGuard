"""D1-02 EPSS评分驱动修复优先级 测试"""
import uuid
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session as SASession
from sqlalchemy import text


_asset_counter = 0

def _seed_finding(db: SASession, epss: float = None, cvss: float = None, cve: str = "CVE-2024-0001", status: str = "NEW") -> int:
    global _asset_counter
    _asset_counter += 1
    tid = str(uuid.uuid4())
    target = f"10.{(_asset_counter >> 16) & 255}.{(_asset_counter >> 8) & 255}.{_asset_counter & 255}"
    db.execute(
        text(
            "INSERT INTO asset (target, target_type, created_at, updated_at) "
            "VALUES (:t, 'IP', datetime('now'), datetime('now'))"
        ),
        {"t": target},
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
            "INSERT INTO scan_finding (scan_task_id, asset, cve, severity, epss_score, cvss_score, status, trace_id, created_at, updated_at) "
            "VALUES (:task_id, '10.0.0.1', :cve, 'HIGH', :epss, :cvss, :status, :tid, datetime('now'), datetime('now'))"
        ),
        {"task_id": task_id, "cve": cve, "epss": epss, "cvss": cvss, "status": status, "tid": ftid},
    )
    row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
    fid = row[0]
    db.commit()
    return fid


def test_findings_list_has_priority_fix(client: TestClient, admin_token: str, db: SASession):
    """findings列表应包含 priority_fix 和 epss_score 字段"""
    _seed_finding(db, epss=0.5, cvss=9.8)

    res = client.get(
        "/api/v1/scan/findings",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    item = data["items"][0]
    assert "epss_score" in item
    assert "priority_fix" in item
    assert item["priority_fix"] is True


def test_findings_low_epss_not_priority(client: TestClient, admin_token: str, db: SASession):
    """EPSS < 0.1 的漏洞不应标记为优先修复"""
    _seed_finding(db, epss=0.05, cvss=5.0)

    res = client.get(
        "/api/v1/scan/findings",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    data = res.json().get("data") or res.json()
    item = data["items"][0]
    assert item["priority_fix"] is False


def test_priority_fix_endpoint(client: TestClient, admin_token: str, db: SASession):
    """GET /scan/findings/priority-fix 应返回EPSS>=0.1的漏洞"""
    _seed_finding(db, epss=0.3, cvss=8.0, cve="CVE-2024-HIGH")
    _seed_finding(db, epss=0.05, cvss=9.0, cve="CVE-2024-LOW")

    res = client.get(
        "/api/v1/scan/findings/priority-fix",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["total"] == 1
    assert data["items"][0]["cve"] == "CVE-2024-HIGH"
    assert "risk_score" in data["items"][0]


def test_priority_fix_sorted_by_risk(client: TestClient, admin_token: str, db: SASession):
    """优先修复列表应按 CVSS×EPSS 降序排列"""
    _seed_finding(db, epss=0.2, cvss=5.0, cve="CVE-LOW-RISK")   # risk=1.0
    _seed_finding(db, epss=0.5, cvss=9.0, cve="CVE-HIGH-RISK")  # risk=4.5

    res = client.get(
        "/api/v1/scan/findings/priority-fix",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    data = res.json().get("data") or res.json()
    assert data["total"] == 2
    assert data["items"][0]["cve"] == "CVE-HIGH-RISK"
    assert data["items"][0]["risk_score"] > data["items"][1]["risk_score"]


def test_priority_fix_empty(client: TestClient, admin_token: str):
    """无EPSS数据时应返回空列表"""
    res = client.get(
        "/api/v1/scan/findings/priority-fix",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["total"] == 0
