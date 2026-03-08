"""
D1-01 CVE 数据库集成与自动关联
支持通过 NVD API 查询 CVE 详情，本地缓存 TTL 24h。
"""
from __future__ import annotations

import json
import time
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

# 本地缓存：{cve_id: {"data": {...}, "ts": timestamp}}
_cve_cache: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 86400  # 24h


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _cache_get(cve_id: str) -> Optional[Dict[str, Any]]:
    entry = _cve_cache.get(cve_id)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(cve_id: str, data: Dict[str, Any]) -> None:
    _cve_cache[cve_id] = {"data": data, "ts": time.time()}


async def enrich_cve(cve_id: str) -> Dict[str, Any]:
    """
    查询 NVD API 补充 CVE 详情。
    返回: {cvss_score, cvss_vector, epss_score, affected_versions, patch_available, patch_url, ...}
    降级：NVD 不可达时返回基于 CVE ID 的降级结果。
    """
    if not cve_id:
        return _fallback_result(cve_id, "empty_cve_id")

    cached = _cache_get(cve_id)
    if cached:
        return {**cached, "from_cache": True}

    try:
        result = await _fetch_nvd(cve_id)
        _cache_set(cve_id, result)
        return {**result, "from_cache": False}
    except Exception as exc:
        fallback = _fallback_result(cve_id, f"nvd_fetch_failed:{exc.__class__.__name__}")
        _cache_set(cve_id, fallback)
        return {**fallback, "from_cache": False}


async def _fetch_nvd(cve_id: str) -> Dict[str, Any]:
    """从 NVD API 2.0 获取 CVE 详情"""
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()

    vulns = data.get("vulnerabilities", [])
    if not vulns:
        return _fallback_result(cve_id, "cve_not_found_in_nvd")

    cve_data = vulns[0].get("cve", {})
    metrics = cve_data.get("metrics", {})

    # CVSS v3.1 优先
    cvss_score = None
    cvss_vector = None
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        metric_list = metrics.get(key, [])
        if metric_list:
            cvss_data = metric_list[0].get("cvssData", {})
            cvss_score = cvss_data.get("baseScore")
            cvss_vector = cvss_data.get("vectorString")
            break

    # 补丁信息
    patch_url = None
    references = cve_data.get("references", [])
    for ref in references:
        tags = ref.get("tags", [])
        if "Patch" in tags or "patch" in str(tags).lower():
            patch_url = ref.get("url")
            break

    # 影响版本
    affected_versions = []
    configs = cve_data.get("configurations", [])
    for config in configs:
        for node in config.get("nodes", []):
            for match in node.get("cpeMatch", []):
                if match.get("vulnerable"):
                    ver_info = match.get("criteria", "")
                    affected_versions.append(ver_info)

    # 描述
    descriptions = cve_data.get("descriptions", [])
    description = ""
    for d in descriptions:
        if d.get("lang") == "en":
            description = d.get("value", "")[:500]
            break

    return {
        "cve_id": cve_id,
        "cvss_score": cvss_score,
        "cvss_vector": cvss_vector,
        "epss_score": None,  # EPSS 需要单独 API，此处预留
        "patch_available": patch_url is not None,
        "patch_url": patch_url,
        "affected_versions": affected_versions[:10],
        "description": description,
        "degraded": False,
        "fallback_reason": None,
    }


async def fetch_epss(cve_id: str) -> Optional[float]:
    """从 FIRST EPSS API 获取 EPSS 分数"""
    try:
        url = f"https://api.first.org/data/v1/epss?cve={cve_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        epss_data = data.get("data", [])
        if epss_data:
            return float(epss_data[0].get("epss", 0))
    except Exception:
        pass
    return None


def _fallback_result(cve_id: str, reason: str) -> Dict[str, Any]:
    """降级结果"""
    return {
        "cve_id": cve_id,
        "cvss_score": None,
        "cvss_vector": None,
        "epss_score": None,
        "patch_available": False,
        "patch_url": None,
        "affected_versions": [],
        "description": "",
        "degraded": True,
        "fallback_reason": reason,
    }


def clear_cache() -> int:
    """清空缓存，返回清理条数"""
    count = len(_cve_cache)
    _cve_cache.clear()
    return count


# ── D1-03: 多源威胁情报聚合 ──

_kev_cache: Dict[str, Any] = {}  # {"data": set(), "ts": 0}


async def fetch_cisa_kev() -> Dict[str, Any]:
    """
    获取 CISA KEV（已知被利用漏洞目录）列表。
    返回 CVE ID 集合，本地缓存 24h。
    """
    if _kev_cache.get("data") and (time.time() - _kev_cache.get("ts", 0)) < _CACHE_TTL:
        return {"kev_ids": _kev_cache["data"], "from_cache": True, "count": len(_kev_cache["data"])}

    try:
        url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        vulns = data.get("vulnerabilities", [])
        kev_ids = {v.get("cveID", "") for v in vulns if v.get("cveID")}
        _kev_cache["data"] = kev_ids
        _kev_cache["ts"] = time.time()

        return {"kev_ids": kev_ids, "from_cache": False, "count": len(kev_ids)}
    except Exception as exc:
        return {"kev_ids": set(), "from_cache": False, "count": 0, "error": str(exc)}


async def check_kev(cve_id: str) -> bool:
    """检查 CVE 是否在 CISA KEV 目录中"""
    result = await fetch_cisa_kev()
    return cve_id.upper() in result.get("kev_ids", set())


class ThreatIntelSource:
    """统一威胁情报源接口"""

    def __init__(self, name: str, source_type: str, endpoint: str, api_key: Optional[str] = None):
        self.name = name
        self.source_type = source_type
        self.endpoint = endpoint
        self.api_key = api_key

    async def query_ip(self, ip: str) -> Dict[str, Any]:
        """查询 IP 情报"""
        try:
            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.endpoint}/indicators/IPv4/{ip}", headers=headers)
                if resp.status_code == 200:
                    return {"source": self.name, "ip": ip, "data": resp.json(), "hit": True}
                return {"source": self.name, "ip": ip, "hit": False}
        except Exception as exc:
            return {"source": self.name, "ip": ip, "hit": False, "error": str(exc)}

    async def query_cve(self, cve_id: str) -> Dict[str, Any]:
        """查询 CVE 情报"""
        try:
            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.endpoint}/indicators/CVE/{cve_id}", headers=headers)
                if resp.status_code == 200:
                    return {"source": self.name, "cve_id": cve_id, "data": resp.json(), "hit": True}
                return {"source": self.name, "cve_id": cve_id, "hit": False}
        except Exception as exc:
            return {"source": self.name, "cve_id": cve_id, "hit": False, "error": str(exc)}


def load_intel_sources_from_plugins(db) -> list:
    """从 plugin_registry 加载 threat_intel 类型插件"""
    from core.database import PluginRegistry
    plugins = db.query(PluginRegistry).filter(
        PluginRegistry.plugin_type == "threat_intel",
        PluginRegistry.enabled == 1,
    ).all()

    sources = []
    for p in plugins:
        config = {}
        if p.config_json:
            try:
                config = json.loads(p.config_json)
            except (json.JSONDecodeError, ValueError):
                pass
        sources.append(ThreatIntelSource(
            name=p.plugin_name,
            source_type="threat_intel",
            endpoint=p.endpoint or "",
            api_key=config.get("api_key"),
        ))
    return sources
