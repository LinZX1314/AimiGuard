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
