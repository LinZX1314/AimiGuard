"""A1-03 扫描工具扩展（Nuclei 集成）测试"""
import pytest
from starlette.testclient import TestClient


# ── scanner.scan_with_nuclei 降级测试 ──

def test_nuclei_graceful_when_not_installed():
    """Nuclei 未安装时应降级返回而非崩溃"""
    import asyncio
    from services.scanner import scanner

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            scanner.scan_with_nuclei("127.0.0.1", template_tags=["cve"])
        )
    finally:
        loop.close()

    assert isinstance(result, dict)
    assert result["success"] is False
    assert "not installed" in result.get("error", "") or "nuclei" in result.get("error", "").lower()
    assert result["total_findings"] == 0


def test_nuclei_template_tags_valid():
    """有效模板标签应被接受"""
    from services.scanner import Scanner
    s = Scanner()
    assert "cve" in s.NUCLEI_TEMPLATE_TAGS
    assert "network" in s.NUCLEI_TEMPLATE_TAGS
    assert "exposure" in s.NUCLEI_TEMPLATE_TAGS
    assert "misconfiguration" in s.NUCLEI_TEMPLATE_TAGS


def test_parse_nuclei_to_findings():
    """Nuclei 结果应正确转换为 scan_finding 格式"""
    from services.scanner import scanner

    nuclei_result = {
        "findings": [
            {
                "template_id": "CVE-2024-1234",
                "host": "10.0.0.1",
                "type": "http",
                "severity": "HIGH",
                "description": "Remote code execution",
            },
            {
                "template_id": "exposed-panel",
                "host": "10.0.0.1",
                "type": "http",
                "severity": "MEDIUM",
                "description": "Admin panel exposed",
            },
        ]
    }

    rows = scanner.parse_nuclei_to_findings(nuclei_result, task_id=1, trace_id="test-trace")
    assert len(rows) == 2
    assert rows[0]["vuln_id"] == "CVE-2024-1234"
    assert rows[0]["severity"] == "HIGH"
    assert rows[1]["vuln_id"] == "exposed-panel"


# ── API 端点测试 ──

def test_nuclei_profiles_api(client: TestClient, admin_token: str):
    """GET /scan/nuclei/profiles 应返回可用模板列表"""
    res = client.get(
        "/api/v1/scan/nuclei/profiles",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert "cve" in data
    assert "network" in data
    assert "full" in data


def test_nuclei_scan_api_graceful(client: TestClient, admin_token: str):
    """POST /scan/nuclei/scan Nuclei未安装时应降级返回"""
    res = client.post(
        "/api/v1/scan/nuclei/scan",
        json={"target": "127.0.0.1", "profile": "cve"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["success"] is False
    assert data["target"] == "127.0.0.1"
    assert data["profile"] == "cve"


def test_nuclei_scan_invalid_profile(client: TestClient, admin_token: str):
    """无效 profile 应返回 400"""
    res = client.post(
        "/api/v1/scan/nuclei/scan",
        json={"target": "127.0.0.1", "profile": "nonexistent"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 400
