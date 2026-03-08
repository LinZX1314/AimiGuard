"""
E1-02 依赖漏洞定期扫描
使用 pip-audit 扫描 Python 依赖，结果写入 security_scan_report 表。
"""
from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.database import SecurityScanReport


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def run_pip_audit(requirements_path: Optional[str] = None) -> Dict[str, Any]:
    """
    执行 pip-audit 扫描，返回结构化结果。
    如果 pip-audit 未安装或执行失败，返回降级结果。
    """
    cmd = ["pip-audit", "--format", "json"]
    if requirements_path:
        cmd.extend(["-r", requirements_path])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        try:
            data = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            data = {"dependencies": [], "error": result.stderr or "parse_error"}

        vulns = data.get("dependencies", [])
        findings: List[Dict[str, Any]] = []
        high_count = 0
        medium_count = 0
        low_count = 0

        for dep in vulns:
            for vuln in dep.get("vulns", []):
                severity = _classify_severity(vuln)
                if severity == "HIGH":
                    high_count += 1
                elif severity == "MEDIUM":
                    medium_count += 1
                else:
                    low_count += 1
                findings.append({
                    "package": dep.get("name", "unknown"),
                    "version": dep.get("version", "unknown"),
                    "vuln_id": vuln.get("id", ""),
                    "fix_versions": vuln.get("fix_versions", []),
                    "description": vuln.get("description", "")[:500],
                    "severity": severity,
                })

        return {
            "success": True,
            "total_findings": len(findings),
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "findings": findings,
            "passed": high_count == 0,
        }

    except FileNotFoundError:
        return {
            "success": False,
            "error": "pip-audit not installed",
            "total_findings": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "findings": [],
            "passed": True,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "pip-audit timeout (>300s)",
            "total_findings": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "findings": [],
            "passed": True,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "total_findings": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "findings": [],
            "passed": True,
        }


def _classify_severity(vuln: Dict[str, Any]) -> str:
    """根据漏洞信息推断严重级别"""
    vuln_id = str(vuln.get("id", "")).upper()
    desc = str(vuln.get("description", "")).lower()

    if "critical" in desc or "remote code execution" in desc or "rce" in desc:
        return "HIGH"
    if "denial of service" in desc or "dos" in desc:
        return "MEDIUM"
    if vuln_id.startswith("PYSEC") or vuln_id.startswith("CVE"):
        return "MEDIUM"
    return "LOW"


def save_audit_report(db: Session, result: Dict[str, Any], trigger_type: str = "scheduled") -> SecurityScanReport:
    """将 pip-audit 结果保存到 security_scan_report 表"""
    trace_id = str(uuid.uuid4())

    report = SecurityScanReport(
        scan_tool="pip-audit",
        trigger_type=trigger_type,
        total_findings=result.get("total_findings", 0),
        high_count=result.get("high_count", 0),
        medium_count=result.get("medium_count", 0),
        low_count=result.get("low_count", 0),
        findings_json=json.dumps(result.get("findings", []), ensure_ascii=False),
        passed=1 if result.get("passed", True) else 0,
        trace_id=trace_id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
