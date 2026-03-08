"""
ORM 模型完整性测试

验证 mvp_schema.sql 中所有表都有对应的 ORM 模型，
且模型可正常创建记录和查询。
"""
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from core.database import (
    AccessAudit,
    AlertEvent,
    AuditExportJob,
    AuditLog,
    BackupJob,
    Base,
    CISecurityScanReport,
    MetricPoint,
    MetricRule,
    RestoreJob,
)


class TestAccessAudit:

    def test_create(self, db):
        row = AccessAudit(
            user_id=1,
            username="admin",
            action="login",
            resource="/api/v1/auth/login",
            result="granted",
            trace_id="aa_test_001",
        )
        db.add(row)
        db.commit()
        assert row.id is not None
        assert row.result == "granted"

    def test_denied(self, db):
        row = AccessAudit(
            action="delete_user",
            resource="/api/v1/users/5",
            permission_required="manage_users",
            result="denied",
            reason="insufficient_permissions",
            trace_id="aa_test_002",
        )
        db.add(row)
        db.commit()
        found = db.query(AccessAudit).filter(AccessAudit.trace_id == "aa_test_002").first()
        assert found.result == "denied"


class TestBackupRestoreJob:

    def test_create_backup(self, db):
        job = BackupJob(
            job_type="full",
            started_at=datetime.now(timezone.utc),
            status="success",
            artifact_uri="backups/test_backup.db",
            checksum="abc123",
            size_bytes=1024,
            triggered_by="admin",
            trace_id="bj_001",
        )
        db.add(job)
        db.commit()
        assert job.id is not None

    def test_create_restore(self, db):
        backup = BackupJob(
            job_type="full",
            started_at=datetime.now(timezone.utc),
            status="success",
            triggered_by="admin",
        )
        db.add(backup)
        db.commit()

        restore = RestoreJob(
            backup_id=backup.id,
            started_at=datetime.now(timezone.utc),
            status="success",
            consistency_check_result="ok",
            triggered_by="admin",
            trace_id="rj_001",
        )
        db.add(restore)
        db.commit()
        assert restore.id is not None
        assert restore.backup_id == backup.id


class TestAlertEvent:

    def test_create(self, db):
        alert = AlertEvent(
            level="critical",
            type="executor_failure",
            source="firewall_executor",
            summary="防火墙同步连续失败 5 次",
            status="NEW",
            trace_id="ae_001",
        )
        db.add(alert)
        db.commit()
        assert alert.id is not None
        assert alert.status == "NEW"

    def test_ack_resolve(self, db):
        alert = AlertEvent(
            level="warning",
            type="high_queue_depth",
            source="scheduler",
            summary="队列堆积超过阈值",
            status="NEW",
            trace_id="ae_002",
        )
        db.add(alert)
        db.commit()

        alert.status = "ACKED"
        alert.acked_by = "operator1"
        alert.acked_at = datetime.now(timezone.utc)
        db.commit()

        found = db.query(AlertEvent).filter(AlertEvent.trace_id == "ae_002").first()
        assert found.status == "ACKED"
        assert found.acked_by == "operator1"


class TestMetrics:

    def test_metric_point(self, db):
        point = MetricPoint(
            metric="api_latency_ms",
            value=42.5,
            labels_json='{"endpoint": "/api/v1/defense/events"}',
            ts=datetime.now(timezone.utc),
        )
        db.add(point)
        db.commit()
        assert point.id is not None

    def test_metric_rule(self, db):
        rule = MetricRule(
            metric="api_error_rate_test",
            operator="gt",
            threshold=0.05,
            window_seconds=300,
            enabled=1,
            alert_level="warning",
        )
        db.add(rule)
        db.commit()
        assert rule.id is not None
        assert rule.threshold == 0.05


class TestAuditExportJob:

    def test_create(self, db):
        job = AuditExportJob(
            filters_json='{"actor": "admin", "date_from": "2026-01-01"}',
            status="pending",
            requested_by="admin",
            reason="monthly_export",
            trace_id="aej_001",
        )
        db.add(job)
        db.commit()
        assert job.id is not None
        assert job.status == "pending"

    def test_complete(self, db):
        job = AuditExportJob(
            filters_json="{}",
            status="completed",
            file_uri="exports/audit_2026.csv",
            file_hash="sha256:abc",
            row_count=1500,
            requested_by="admin",
            progress=1.0,
        )
        db.add(job)
        db.commit()
        assert job.row_count == 1500


class TestCISecurityScanReport:

    def test_create_bandit(self, db):
        report = CISecurityScanReport(
            scan_tool="bandit",
            trigger_type="pr",
            branch="feature/auth-fix",
            commit_sha="abc123def",
            total_findings=3,
            high_count=1,
            medium_count=2,
            low_count=0,
            passed=0,
            trace_id="ci_001",
        )
        db.add(report)
        db.commit()
        assert report.id is not None
        assert report.passed == 0

    def test_create_semgrep(self, db):
        report = CISecurityScanReport(
            scan_tool="semgrep",
            trigger_type="manual",
            total_findings=0,
            passed=1,
            trace_id="ci_002",
        )
        db.add(report)
        db.commit()
        assert report.passed == 1


class TestAllTablesHaveORM:
    """验证所有 SQL 表都有对应的 ORM 模型"""

    def test_table_count(self):
        table_names = set(Base.metadata.tables.keys())
        expected_sql_tables = {
            "user", "role", "permission", "user_role", "role_permission",
            "threat_event", "execution_task", "scan_task", "scan_finding",
            "firewall_sync_task", "ai_decision_log", "ai_report",
            "audit_log", "plugin_registry", "system_config_snapshot",
            "device", "asset", "credential", "ai_chat_session",
            "ai_chat_message", "ai_tts_task", "push_channel",
            "model_profile", "collector_config",
            "workflow_definition", "workflow_version",
            "workflow_run", "workflow_step_run",
            "release_history", "fix_ticket", "security_scan_report",
            "honeypot_config", "honeytoken", "plugin_call_log",
            "prompt_template", "ip_whitelist",
            "access_audit", "backup_job", "restore_job",
            "alert_event", "metric_point", "metric_rule",
            "audit_export_job", "ci_security_scan_report",
        }
        missing = expected_sql_tables - table_names
        assert not missing, f"ORM models missing for tables: {missing}"
