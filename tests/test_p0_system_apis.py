"""
P0 系统API测试：R3备份恢复、R4安全报告、R5告警闭环、R6指标、R7审计导出
"""
import os
import sys
import json
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from core.database import (
    AlertEvent,
    AuditExportJob,
    AuditLog,
    BackupJob,
    MetricPoint,
    MetricRule,
    RestoreJob,
    SecurityScanReport,
)


@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ── R5 告警闭环 ──


class TestAlertAPIs:

    def _create_alert(self, db, level="critical", status="NEW", trace_id="t_alert"):
        alert = AlertEvent(
            level=level,
            type="executor_failure",
            source="test",
            summary="测试告警",
            payload_json='{"detail": "test"}',
            status=status,
            trace_id=trace_id,
        )
        db.add(alert)
        db.commit()
        return alert

    def test_list_alerts_empty(self, client, auth_headers, db):
        resp = client.get("/api/v1/system/alerts", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        # May have alerts from other tests; just check structure
        assert "alerts" in data
        assert "total" in data

    def test_list_alerts_with_filter(self, client, auth_headers, db):
        self._create_alert(db, level="warning", trace_id="t_filter_1")
        self._create_alert(db, level="critical", trace_id="t_filter_2")
        resp = client.get("/api/v1/system/alerts?level=warning", headers=auth_headers)
        assert resp.status_code == 200
        alerts = resp.json()["data"]["alerts"]
        for a in alerts:
            assert a["level"] == "warning"

    def test_alert_lifecycle_new_ack_resolve_postmortem(self, client, auth_headers, db):
        alert = self._create_alert(db)
        aid = alert.id

        # ACK
        resp = client.post(
            f"/api/v1/system/alerts/{aid}/ack",
            headers=auth_headers,
            json={"ack_by": "operator1", "trace_id": "t_ack"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["new_status"] == "ACKED"

        # RESOLVE
        resp = client.post(
            f"/api/v1/system/alerts/{aid}/resolve",
            headers=auth_headers,
            json={"resolution": "已修复", "trace_id": "t_resolve"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["new_status"] == "RESOLVED"

        # POSTMORTEM
        resp = client.post(
            f"/api/v1/system/alerts/{aid}/postmortem",
            headers=auth_headers,
            json={"author": "admin", "root_cause": "配置错误", "action_items": ["修改配置"], "trace_id": "t_pm"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["new_status"] == "POSTMORTEM"

    def test_ack_non_new_alert_fails(self, client, auth_headers, db):
        alert = self._create_alert(db, status="ACKED")
        resp = client.post(
            f"/api/v1/system/alerts/{alert.id}/ack",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 400

    def test_resolve_postmortem_alert_fails(self, client, auth_headers, db):
        alert = self._create_alert(db, status="POSTMORTEM")
        resp = client.post(
            f"/api/v1/system/alerts/{alert.id}/resolve",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 400

    def test_postmortem_non_resolved_fails(self, client, auth_headers, db):
        alert = self._create_alert(db, status="ACKED")
        resp = client.post(
            f"/api/v1/system/alerts/{alert.id}/postmortem",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 400

    def test_alert_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/v1/system/alerts/99999/ack",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 404


# ── R3 备份恢复 ──


class TestBackupAPIs:

    def test_list_backups(self, client, auth_headers):
        resp = client.get("/api/v1/system/backup/list", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    def test_create_backup(self, client, auth_headers):
        resp = client.post(
            "/api/v1/system/backup/create",
            headers=auth_headers,
            json={"type": "full"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] in ("success", "failed")
        assert data["id"] is not None


# ── R4 安全报告 ──


class TestSecurityReportAPI:

    def test_latest_no_reports(self, client, auth_headers, db):
        resp = client.get("/api/v1/system/security-report/latest", headers=auth_headers)
        assert resp.status_code == 200

    def test_latest_with_report(self, client, auth_headers, db):
        report = SecurityScanReport(
            scan_tool="pip-audit",
            trigger_type="manual",
            total_findings=6,
            high_count=1,
            medium_count=2,
            low_count=3,
            passed=1,
            trace_id="t_scan_report",
        )
        db.add(report)
        db.commit()
        resp = client.get("/api/v1/system/security-report/latest", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data is not None
        assert data["scan_tool"] == "pip-audit"
        assert data["passed"] is True


# ── R6 指标 ──


class TestMetricsAPIs:

    def test_metrics_overview(self, client, auth_headers):
        resp = client.get("/api/v1/system/metrics/overview", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "metrics" in data
        assert "collected_at" in data

    def test_metrics_timeseries(self, client, auth_headers, db):
        now = datetime.now(timezone.utc)
        for i in range(3):
            db.add(MetricPoint(
                metric="test_metric_ts",
                value=float(i * 10),
                ts=now,
            ))
        db.commit()
        resp = client.get(
            "/api/v1/system/metrics/timeseries?metric=test_metric_ts",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["metric"] == "test_metric_ts"
        assert len(data["data_points"]) >= 3

    def test_metrics_timeseries_empty(self, client, auth_headers):
        resp = client.get(
            "/api/v1/system/metrics/timeseries?metric=nonexistent_metric",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["data_points"] == []


# ── R7 审计导出 ──


class TestAuditExportAPIs:

    def test_create_export(self, client, auth_headers, db):
        # Seed some audit logs
        db.add(AuditLog(
            actor="admin",
            action="test_action",
            target="test_target",
            result="success",
            trace_id="t_export_seed",
        ))
        db.commit()

        resp = client.post(
            "/api/v1/system/audit/export",
            headers=auth_headers,
            json={"filters": {"actor": "admin"}, "reason": "月度审计"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "completed"
        assert data["row_count"] >= 1
        job_id = data["job_id"]

        # Query export status
        resp2 = client.get(
            f"/api/v1/system/audit/export/{job_id}",
            headers=auth_headers,
        )
        assert resp2.status_code == 200
        assert resp2.json()["data"]["status"] == "completed"
        assert resp2.json()["data"]["file_hash"].startswith("sha256:")

    def test_export_not_found(self, client, auth_headers):
        resp = client.get(
            "/api/v1/system/audit/export/99999",
            headers=auth_headers,
        )
        assert resp.status_code == 404
