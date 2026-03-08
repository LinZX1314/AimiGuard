"""E1-01 CI/CD 安全扫描报告 测试"""
import json
import pytest
from starlette.testclient import TestClient


def test_submit_report(client: TestClient, admin_token: str):
    """提交安全扫描报告"""
    res = client.post(
        "/api/v1/security-scan/reports",
        json={
            "scan_tool": "bandit",
            "trigger_type": "pr",
            "branch": "feature/auth",
            "commit_sha": "abc123",
            "total_findings": 5,
            "high_count": 1,
            "medium_count": 3,
            "low_count": 1,
            "passed": False,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["scan_tool"] == "bandit"
    assert data["high_count"] == 1
    assert data["passed"] is False


def test_list_reports_empty(client: TestClient, admin_token: str):
    """无报告时应返回空列表"""
    res = client.get(
        "/api/v1/security-scan/reports",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["total"] == 0


def test_list_reports_filter_tool(client: TestClient, admin_token: str):
    """按工具筛选报告"""
    client.post(
        "/api/v1/security-scan/reports",
        json={"scan_tool": "bandit", "total_findings": 2, "high_count": 0},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        "/api/v1/security-scan/reports",
        json={"scan_tool": "semgrep", "total_findings": 1, "high_count": 0},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    res = client.get(
        "/api/v1/security-scan/reports?scan_tool=bandit",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["total"] == 1
    assert data["items"][0]["scan_tool"] == "bandit"


def test_get_report_detail(client: TestClient, admin_token: str):
    """获取报告详情含 findings_json"""
    findings = json.dumps([{"file": "api.py", "line": 10, "issue": "hardcoded password"}])
    r = client.post(
        "/api/v1/security-scan/reports",
        json={
            "scan_tool": "bandit",
            "total_findings": 1,
            "high_count": 1,
            "findings_json": findings,
            "passed": False,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    rid = (r.json().get("data") or r.json())["id"]

    res = client.get(
        f"/api/v1/security-scan/reports/{rid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["findings_json"] is not None
    parsed = json.loads(data["findings_json"])
    assert len(parsed) == 1


def test_get_report_not_found(client: TestClient, admin_token: str):
    """不存在的报告应 404"""
    res = client.get(
        "/api/v1/security-scan/reports/99999",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 404
