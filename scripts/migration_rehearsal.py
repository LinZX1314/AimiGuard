#!/usr/bin/env python3
"""
Step 10.1 — 数据迁移演练与回滚演练脚本

功能：
  1. 从 mvp_schema.sql 创建全新数据库（模拟首次部署）
  2. 执行 init_db 样例数据写入
  3. 执行增量迁移（add_session_security / add_workflow_tables_v1）
  4. 校验全量表、索引、列是否齐全
  5. 插入业务样本并验证可读
  6. 创建备份（SQLite 文件复制 + SHA256 校验）
  7. 执行回滚迁移（rollback_workflow_tables_v1）并验证受影响表已删除
  8. 从备份恢复并验证一致性
  9. 输出演练报告

用法：
  python scripts/migration_rehearsal.py           # 完整演练
  python scripts/migration_rehearsal.py --quick   # 快速模式（跳过备份恢复）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_SCHEMA = PROJECT_ROOT / "sql" / "mvp_schema.sql"
MIGRATIONS_DIR = PROJECT_ROOT / "backend" / "migrations"


# ---------------------------------------------------------------------------
# Expected schema baseline (tables that must exist after full migration)
# ---------------------------------------------------------------------------
EXPECTED_TABLES = {
    # Core business
    "threat_event", "execution_task", "asset", "scan_task", "scan_finding",
    "device", "credential", "ai_decision_log",
    "ai_chat_session", "ai_chat_message", "ai_report", "ai_tts_task",
    "plugin_registry", "push_channel", "firewall_sync_task", "model_profile",
    # Workflow (M1-02)
    "workflow_definition", "workflow_version", "workflow_run", "workflow_step_run",
    # P0 system
    "release_history", "system_config_snapshot",
    # RBAC
    "role", "permission", "role_permission", "user", "user_role", "access_audit",
    # Backup / restore
    "backup_job", "restore_job",
    # Security / alerts / metrics / audit
    "security_scan_report", "alert_event", "metric_point", "metric_rule",
    "audit_log", "audit_export_job",
    # Extended
    "fix_ticket", "honeypot_config", "honeytoken", "plugin_call_log", "prompt_template",
    "ci_security_scan_report",
}

WORKFLOW_TABLES = {
    "workflow_definition", "workflow_version", "workflow_run", "workflow_step_run",
}

# Key columns to spot-check per table (table -> set of required columns)
KEY_COLUMNS = {
    "threat_event": {"id", "ip", "source", "ai_score", "status", "trace_id", "false_positive_by"},
    "execution_task": {"id", "event_id", "action", "state", "retry_count", "approved_by", "trace_id"},
    "ai_decision_log": {"id", "event_id", "model_name", "prompt_hash", "inference_ms", "trace_id"},
    "scan_finding": {"id", "scan_task_id", "asset", "severity", "exploitability_json", "cvss_score"},
    "audit_log": {"id", "actor", "action", "result", "trace_id", "integrity_hash", "prev_hash"},
    "workflow_definition": {"id", "workflow_key", "name", "definition_state"},
    "workflow_run": {"id", "workflow_id", "run_state", "trace_id"},
}


@dataclass
class RehearsalResult:
    step: str
    success: bool
    duration_ms: float = 0.0
    detail: str = ""
    errors: list[str] = field(default_factory=list)


class MigrationRehearsal:
    """Orchestrates the full migration / rollback / restore rehearsal."""

    def __init__(self, db_path: Path, quick: bool = False):
        self.db_path = db_path
        self.backup_path = db_path.with_suffix(".db.bak")
        self.quick = quick
        self.results: list[RehearsalResult] = []

    # -- helpers -------------------------------------------------------------
    def _run_step(self, name: str, fn):
        t0 = time.perf_counter()
        result = RehearsalResult(step=name, success=False)
        try:
            fn(result)
            result.success = len(result.errors) == 0
        except Exception as exc:
            result.errors.append(f"Exception: {exc}")
        result.duration_ms = (time.perf_counter() - t0) * 1000
        self.results.append(result)
        status = "✅" if result.success else "❌"
        print(f"  {status} {name} ({result.duration_ms:.0f}ms)")
        if result.errors:
            for e in result.errors:
                print(f"     ↳ {e}")

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _table_names(self, conn: sqlite3.Connection) -> set[str]:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {r[0] for r in rows}

    def _column_names(self, conn: sqlite3.Connection, table: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {r[1] for r in rows}

    def _file_sha256(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    # -- steps ---------------------------------------------------------------
    def step1_create_schema(self, r: RehearsalResult):
        """Apply mvp_schema.sql to fresh DB."""
        if not SQL_SCHEMA.exists():
            r.errors.append(f"Schema file not found: {SQL_SCHEMA}")
            return
        conn = self._conn()
        sql = SQL_SCHEMA.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.close()
        r.detail = f"Schema applied from {SQL_SCHEMA.name}"

    def step2_insert_sample_data(self, r: RehearsalResult):
        """Insert minimal sample data (users, roles, permissions)."""
        conn = self._conn()
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.cursor()
        # Roles
        for role_name in ("admin", "operator", "viewer"):
            cur.execute(
                "INSERT INTO role (name, description, created_at, updated_at) VALUES (?,?,?,?)",
                (role_name, f"{role_name} role", now, now),
            )
        # Permissions
        cur.execute(
            "INSERT INTO permission (name, resource, action, description, created_at, updated_at) "
            "VALUES ('view_events','defense','view','查看事件',?,?)",
            (now, now),
        )
        # User
        cur.execute(
            "INSERT INTO user (username, password_hash, email, full_name, enabled, created_at, updated_at) "
            "VALUES ('admin','hash','a@b.c','Admin',1,?,?)",
            (now, now),
        )
        # Release history
        cur.execute(
            "INSERT INTO release_history (version, git_commit, schema_version, deploy_env, status, deployed_by, created_at, updated_at) "
            "VALUES ('v0.1.0','abc123','1.0.0','dev','active','system',?,?)",
            (now, now),
        )
        # Threat event (business sample)
        cur.execute(
            "INSERT INTO threat_event (ip, source, status, trace_id, created_at, updated_at) "
            "VALUES ('10.0.0.1','hfish','PENDING','rehearsal_001',?,?)",
            (now, now),
        )
        # Audit log
        cur.execute(
            "INSERT INTO audit_log (actor, action, target, result, trace_id, created_at) "
            "VALUES ('system','migration_rehearsal','database','success','rehearsal_001',?)",
            (now,),
        )
        conn.commit()
        conn.close()
        r.detail = "Sample data inserted (roles, user, event, audit)"

    def step3_run_migrations(self, r: RehearsalResult):
        """Run incremental migrations."""
        # add_session_security
        sys.path.insert(0, str(MIGRATIONS_DIR.parent))
        session_sec = MIGRATIONS_DIR / "add_session_security.py"
        if session_sec.exists():
            # Directly apply via sqlite3 since the script expects specific db path
            conn = self._conn()
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(ai_chat_session)")
            cols = {row[1] for row in cur.fetchall()}
            if "user_id" not in cols:
                cur.execute("ALTER TABLE ai_chat_session ADD COLUMN user_id INTEGER REFERENCES user(id)")
            if "expires_at" not in cols:
                cur.execute("ALTER TABLE ai_chat_session ADD COLUMN expires_at DATETIME")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_chat_session_user_id ON ai_chat_session(user_id)")
            conn.commit()
            conn.close()
            r.detail += " | session_security applied"

        # add_workflow_tables_v1
        wf_mig = MIGRATIONS_DIR / "add_workflow_tables_v1.py"
        if wf_mig.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("wf_mig", str(wf_mig))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.migrate(str(self.db_path))
            r.detail += " | workflow_tables_v1 applied"

    def step4_apply_lightweight_migrations(self, r: RehearsalResult):
        """Simulate the _ensure_sqlite_column calls from database.py init_db."""
        conn = self._conn()
        cur = conn.cursor()

        def _cols(table: str) -> set[str]:
            return {row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}

        def _ensure(table: str, col: str, col_type: str):
            if col not in _cols(table):
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")

        # Replicate all _ensure_sqlite_column calls from database.py
        _ensure("scan_finding", "mac_address", "VARCHAR")
        _ensure("scan_finding", "vendor", "VARCHAR")
        _ensure("scan_finding", "hostname", "VARCHAR")
        _ensure("scan_finding", "state", "VARCHAR")
        _ensure("scan_finding", "os_type", "VARCHAR")
        _ensure("scan_finding", "os_accuracy", "VARCHAR")

        _ensure("threat_event", "service_port", "VARCHAR")
        _ensure("threat_event", "ip_location", "VARCHAR")
        _ensure("threat_event", "client_id", "VARCHAR")
        _ensure("threat_event", "client_name", "VARCHAR")
        _ensure("threat_event", "false_positive_by", "VARCHAR")
        _ensure("threat_event", "false_positive_reason", "TEXT")
        _ensure("threat_event", "false_positive_at", "TEXT")

        _ensure("execution_task", "approved_by", "VARCHAR")

        _ensure("ai_decision_log", "prompt_hash", "VARCHAR")
        _ensure("ai_decision_log", "inference_ms", "REAL")
        _ensure("ai_decision_log", "model_params", "TEXT")
        _ensure("ai_decision_log", "prompt_tokens", "INTEGER")
        _ensure("ai_decision_log", "completion_tokens", "INTEGER")

        _ensure("audit_log", "integrity_hash", "VARCHAR")
        _ensure("audit_log", "prev_hash", "VARCHAR")

        _ensure("scan_finding", "exploitability_json", "TEXT")
        _ensure("scan_finding", "cvss_score", "REAL")
        _ensure("scan_finding", "cvss_vector", "TEXT")
        _ensure("scan_finding", "epss_score", "REAL")
        _ensure("scan_finding", "patch_url", "TEXT")
        _ensure("scan_finding", "enriched_at", "TEXT")

        _ensure("plugin_registry", "declared_permissions", "TEXT")
        _ensure("plugin_registry", "actual_calls_json", "TEXT")
        _ensure("plugin_registry", "risk_score", "INTEGER")

        _ensure("fix_ticket", "finding_id", "INTEGER")
        _ensure("fix_ticket", "priority", "VARCHAR")
        _ensure("fix_ticket", "assignee", "VARCHAR")
        _ensure("fix_ticket", "status", "VARCHAR")
        _ensure("fix_ticket", "due_date", "VARCHAR")
        _ensure("fix_ticket", "resolution_note", "TEXT")
        _ensure("fix_ticket", "closed_at", "VARCHAR")

        conn.commit()
        conn.close()
        r.detail = "Lightweight column migrations applied"

    def step5_validate_schema(self, r: RehearsalResult):
        """Validate all expected tables, indexes, and key columns exist."""
        conn = self._conn()
        tables = self._table_names(conn)

        missing_tables = EXPECTED_TABLES - tables
        if missing_tables:
            r.errors.append(f"Missing tables: {sorted(missing_tables)}")

        # Validate key columns
        for table, required_cols in KEY_COLUMNS.items():
            if table not in tables:
                continue
            actual_cols = self._column_names(conn, table)
            missing_cols = required_cols - actual_cols
            if missing_cols:
                r.errors.append(f"{table}: missing columns {sorted(missing_cols)}")

        # Validate indexes exist
        idx_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        idx_names = {r[0] for r in idx_rows}
        critical_indexes = {
            "idx_threat_event_status", "idx_threat_event_trace_id",
            "idx_execution_task_state", "idx_audit_log_trace_id",
            "idx_scan_task_state", "idx_workflow_run_state",
        }
        missing_idx = critical_indexes - idx_names
        if missing_idx:
            r.errors.append(f"Missing indexes: {sorted(missing_idx)}")

        conn.close()
        r.detail = f"Validated {len(tables)} tables, {len(idx_names)} indexes"

    def step6_validate_data_readable(self, r: RehearsalResult):
        """Verify inserted sample data is readable."""
        conn = self._conn()
        checks = [
            ("SELECT COUNT(*) FROM role", 3, "roles"),
            ("SELECT COUNT(*) FROM user", 1, "users"),
            ("SELECT COUNT(*) FROM threat_event WHERE trace_id='rehearsal_001'", 1, "threat_event"),
            ("SELECT COUNT(*) FROM audit_log WHERE trace_id='rehearsal_001'", 1, "audit_log"),
            ("SELECT COUNT(*) FROM release_history WHERE version='v0.1.0'", 1, "release_history"),
        ]
        for sql, expected, label in checks:
            actual = conn.execute(sql).fetchone()[0]
            if actual != expected:
                r.errors.append(f"{label}: expected {expected} rows, got {actual}")
        conn.close()
        r.detail = f"All {len(checks)} data readability checks passed"

    def step7_create_backup(self, r: RehearsalResult):
        """Create backup via file copy + SHA256."""
        shutil.copy2(str(self.db_path), str(self.backup_path))
        orig_hash = self._file_sha256(self.db_path)
        bak_hash = self._file_sha256(self.backup_path)
        if orig_hash != bak_hash:
            r.errors.append(f"Backup hash mismatch: {orig_hash} vs {bak_hash}")
        r.detail = f"Backup created, SHA256={orig_hash[:16]}..."

    def step8_rollback_workflow(self, r: RehearsalResult):
        """Rollback workflow tables and verify they are gone."""
        wf_rb = MIGRATIONS_DIR / "rollback_workflow_tables_v1.py"
        if not wf_rb.exists():
            r.errors.append("Rollback script not found")
            return

        import importlib.util
        spec = importlib.util.spec_from_file_location("wf_rb", str(wf_rb))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.rollback(str(self.db_path))

        # Verify tables removed
        conn = self._conn()
        tables = self._table_names(conn)
        remaining = WORKFLOW_TABLES & tables
        if remaining:
            r.errors.append(f"Workflow tables still exist after rollback: {sorted(remaining)}")

        # Verify other tables untouched
        core_tables = {"threat_event", "execution_task", "audit_log", "user", "role"}
        missing_core = core_tables - tables
        if missing_core:
            r.errors.append(f"Core tables damaged by rollback: {sorted(missing_core)}")

        conn.close()
        r.detail = "Workflow tables rolled back; core tables intact"

    def step9_restore_from_backup(self, r: RehearsalResult):
        """Restore from backup and validate consistency."""
        if not self.backup_path.exists():
            r.errors.append("Backup file not found")
            return

        # Restore
        shutil.copy2(str(self.backup_path), str(self.db_path))

        # Verify tables are back
        conn = self._conn()
        tables = self._table_names(conn)
        missing_wf = WORKFLOW_TABLES - tables
        if missing_wf:
            r.errors.append(f"Workflow tables not restored: {sorted(missing_wf)}")

        # Verify data integrity
        event_count = conn.execute(
            "SELECT COUNT(*) FROM threat_event WHERE trace_id='rehearsal_001'"
        ).fetchone()[0]
        if event_count != 1:
            r.errors.append(f"Data integrity check failed: threat_event count={event_count}")

        audit_count = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE trace_id='rehearsal_001'"
        ).fetchone()[0]
        if audit_count != 1:
            r.errors.append(f"Data integrity check failed: audit_log count={audit_count}")

        conn.close()
        r.detail = "Restored from backup; data integrity verified"

    def step10_idempotent_rerun(self, r: RehearsalResult):
        """Re-run schema + migrations to verify idempotency."""
        conn = self._conn()
        sql = SQL_SCHEMA.read_text(encoding="utf-8")
        try:
            conn.executescript(sql)
        except Exception as exc:
            r.errors.append(f"Schema re-run failed: {exc}")

        # Re-run lightweight migrations
        cur = conn.cursor()

        def _cols(table: str) -> set[str]:
            return {row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}

        def _ensure(table: str, col: str, col_type: str):
            if col not in _cols(table):
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")

        try:
            _ensure("threat_event", "false_positive_by", "VARCHAR")
            _ensure("execution_task", "approved_by", "VARCHAR")
            conn.commit()
        except Exception as exc:
            r.errors.append(f"Idempotent migration re-run failed: {exc}")

        # Verify data still intact
        count = conn.execute("SELECT COUNT(*) FROM user").fetchone()[0]
        if count < 1:
            r.errors.append(f"Data lost after idempotent rerun: user count={count}")

        conn.close()
        r.detail = "Idempotent re-run passed; data intact"

    # -- orchestrator --------------------------------------------------------
    def run(self) -> bool:
        print("=" * 60)
        print("  Step 10.1 数据迁移演练与回滚演练")
        print(f"  Database: {self.db_path}")
        print(f"  Schema:   {SQL_SCHEMA}")
        print(f"  Mode:     {'quick' if self.quick else 'full'}")
        print("=" * 60)

        self._run_step("1. 建表（mvp_schema.sql）", self.step1_create_schema)
        self._run_step("2. 写入样例数据", self.step2_insert_sample_data)
        self._run_step("3. 执行增量迁移", self.step3_run_migrations)
        self._run_step("4. 轻量列迁移", self.step4_apply_lightweight_migrations)
        self._run_step("5. 校验表/索引/列完整性", self.step5_validate_schema)
        self._run_step("6. 校验数据可读", self.step6_validate_data_readable)

        if not self.quick:
            self._run_step("7. 创建备份（SHA256 校验）", self.step7_create_backup)
            self._run_step("8. 回滚工作流表", self.step8_rollback_workflow)
            self._run_step("9. 从备份恢复并校验一致性", self.step9_restore_from_backup)

        self._run_step("10. 幂等重跑校验", self.step10_idempotent_rerun)

        # -- report ----------------------------------------------------------
        total = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        failed = total - passed
        total_ms = sum(r.duration_ms for r in self.results)

        print()
        print("=" * 60)
        print(f"  演练结果: {passed}/{total} 通过  |  耗时 {total_ms:.0f}ms")
        if failed:
            print(f"  ❌ {failed} 步骤失败")
        else:
            print("  ✅ 全部通过")
        print("=" * 60)

        return failed == 0

    def generate_report(self) -> dict:
        """Generate structured rehearsal report."""
        return {
            "rehearsal": "step10_1_migration_rollback",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "db_path": str(self.db_path),
            "mode": "quick" if self.quick else "full",
            "steps": [
                {
                    "step": r.step,
                    "success": r.success,
                    "duration_ms": round(r.duration_ms, 1),
                    "detail": r.detail,
                    "errors": r.errors,
                }
                for r in self.results
            ],
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r.success),
                "failed": sum(1 for r in self.results if not r.success),
                "total_ms": round(sum(r.duration_ms for r in self.results), 1),
            },
        }


def run_rehearsal(db_path: Optional[str] = None, quick: bool = False) -> bool:
    """Entry point for programmatic use (e.g. from tests)."""
    if db_path:
        path = Path(db_path)
    else:
        tmp = tempfile.mkdtemp(prefix="aimiguan_rehearsal_")
        path = Path(tmp) / "rehearsal.db"

    rehearsal = MigrationRehearsal(path, quick=quick)
    success = rehearsal.run()

    report = rehearsal.generate_report()
    report_path = path.with_suffix(".report.json")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n📄 演练报告: {report_path}")

    # Cleanup backup
    bak = path.with_suffix(".db.bak")
    if bak.exists():
        bak.unlink()

    return success


def main():
    parser = argparse.ArgumentParser(description="Step 10.1 数据迁移演练与回滚演练")
    parser.add_argument("--quick", action="store_true", help="快速模式（跳过备份恢复）")
    parser.add_argument("--db", type=str, default=None, help="指定数据库路径（默认使用临时目录）")
    args = parser.parse_args()

    success = run_rehearsal(db_path=args.db, quick=args.quick)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
