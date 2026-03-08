"""E1-02 依赖漏洞定期扫描 测试"""
import pytest
from starlette.testclient import TestClient


# ── dep_audit 服务逻辑 ──

def test_run_pip_audit_graceful():
    """pip-audit 不可用时应降级返回而非崩溃"""
    from services.dep_audit import run_pip_audit
    result = run_pip_audit()
    assert isinstance(result, dict)
    assert "total_findings" in result
    assert "passed" in result


def test_classify_severity():
    """严重级别分类"""
    from services.dep_audit import _classify_severity
    assert _classify_severity({"id": "CVE-2024-001", "description": "remote code execution"}) == "HIGH"
    assert _classify_severity({"id": "PYSEC-2024-001", "description": "some issue"}) == "MEDIUM"
    assert _classify_severity({"id": "UNKNOWN", "description": "minor issue"}) == "LOW"


def test_save_audit_report(db):
    """保存审计报告到数据库"""
    from services.dep_audit import save_audit_report
    result = {
        "total_findings": 2,
        "high_count": 1,
        "medium_count": 1,
        "low_count": 0,
        "findings": [{"package": "requests", "vuln_id": "CVE-2024-001"}],
        "passed": False,
    }
    report = save_audit_report(db, result, trigger_type="manual")
    assert report.id is not None
    assert report.scan_tool == "pip-audit"
    assert report.high_count == 1
    assert report.passed == 0


# ── API 端点 ──

def test_dep_audit_api(client: TestClient, admin_token: str):
    """POST /security-scan/dep-audit 应触发扫描并返回报告"""
    res = client.post(
        "/api/v1/security-scan/dep-audit",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["scan_tool"] == "pip-audit"
    assert "scan_success" in data


def test_dep_audit_report_in_list(client: TestClient, admin_token: str):
    """dep-audit 报告应出现在报告列表中"""
    client.post(
        "/api/v1/security-scan/dep-audit",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    res = client.get(
        "/api/v1/security-scan/reports?scan_tool=pip-audit",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["total"] >= 1
