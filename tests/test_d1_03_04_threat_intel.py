"""D1-03 多源威胁情报聚合 + D1-04 威胁情报看板 测试"""
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session as SASession
from sqlalchemy import text


# ── D1-03: 威胁情报源管理 ──

def test_register_intel_source(client: TestClient, admin_token: str):
    """注册威胁情报源"""
    res = client.post(
        "/api/v1/threat-intel/sources",
        json={"plugin_name": "otx_test", "endpoint": "https://otx.alienvault.com/api/v1"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["plugin_name"] == "otx_test"
    assert data["plugin_type"] == "threat_intel"


def test_register_duplicate_source(client: TestClient, admin_token: str):
    """重复注册应409"""
    client.post(
        "/api/v1/threat-intel/sources",
        json={"plugin_name": "otx_dup", "endpoint": "https://otx.example.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    res = client.post(
        "/api/v1/threat-intel/sources",
        json={"plugin_name": "otx_dup", "endpoint": "https://otx.example.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 409


def test_list_intel_sources(client: TestClient, admin_token: str):
    """查询情报源列表"""
    client.post(
        "/api/v1/threat-intel/sources",
        json={"plugin_name": "src1", "endpoint": "https://a.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    res = client.get(
        "/api/v1/threat-intel/sources",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["total"] >= 1


# ── D1-03: 情报查询 ──

def test_query_ip_intel(client: TestClient, admin_token: str):
    """聚合查询IP情报（无源时返回空结果）"""
    res = client.post(
        "/api/v1/threat-intel/query/ip",
        json={"ip": "8.8.8.8"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["ip"] == "8.8.8.8"
    assert "sources_queried" in data


def test_query_cve_intel(client: TestClient, admin_token: str):
    """聚合查询CVE情报 + KEV检查"""
    res = client.post(
        "/api/v1/threat-intel/query/cve",
        json={"cve_id": "CVE-2024-0001"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["cve_id"] == "CVE-2024-0001"
    assert "in_cisa_kev" in data


# ── D1-03: ThreatIntelSource 类 ──

def test_threat_intel_source_query_ip():
    """ThreatIntelSource.query_ip 降级"""
    import asyncio
    from services.threat_intel import ThreatIntelSource

    src = ThreatIntelSource("test", "threat_intel", "https://invalid.example.com")
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(src.query_ip("1.2.3.4"))
    finally:
        loop.close()

    assert result["hit"] is False
    assert result["source"] == "test"


def test_load_intel_sources_from_plugins(client: TestClient, admin_token: str, db: SASession):
    """从plugin_registry加载情报源"""
    from services.threat_intel import load_intel_sources_from_plugins

    db.execute(
        text(
            "INSERT INTO plugin_registry (plugin_name, plugin_type, endpoint, enabled, created_at, updated_at) "
            "VALUES ('test_intel', 'threat_intel', 'https://api.test.com', 1, datetime('now'), datetime('now'))"
        )
    )
    db.commit()

    sources = load_intel_sources_from_plugins(db)
    assert len(sources) >= 1
    assert sources[0].name == "test_intel"


# ── D1-04: 威胁情报看板 ──

def test_threat_intel_overview(client: TestClient, admin_token: str):
    """GET /threat-intel/overview 应返回看板数据"""
    res = client.get(
        "/api/v1/threat-intel/overview",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert "total_findings" in data
    assert "unique_cves" in data
    assert "kev_total" in data
    assert "priority_fix_count" in data
    assert "epss_top10" in data
