"""
Step 10.5 / 10.7 — 灰度发布核心指标观察 & SLO 达标验证

验证：
  - 所有核心 API 端点可达且返回 200
  - P95 延迟 ≤ 500ms
  - 无 5xx 错误
  - AI 降级兜底正常工作
  - 防火墙队列不积压
  - 审计日志可写入
"""
import time
from datetime import datetime, timezone

import pytest
from sqlalchemy import text


@pytest.fixture(scope="module")
def auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    token = resp.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Step 10.5 — 灰度发布核心端点可达性
# ---------------------------------------------------------------------------

class TestCanaryCoreEndpoints:
    """All core endpoints must be reachable and return 200."""

    ENDPOINTS = [
        "/api/health",
        "/api/v1/defense/events",
        "/api/v1/defense/pending",
        "/api/v1/scan/assets",
        "/api/v1/scan/tasks",
        "/api/v1/scan/findings",
        "/api/v1/ai/decisions",
        "/api/v1/ai/sessions",
        "/api/v1/overview/metrics",
        "/api/v1/overview/todos",
        "/api/v1/overview/chain-status",
        "/api/v1/firewall/tasks",
        "/api/v1/workflows",
        "/api/v1/system/audit/logs",
    ]

    def test_all_core_endpoints_200(self, client, auth_headers):
        """Every core endpoint must return 200 OK."""
        failures = []
        for ep in self.ENDPOINTS:
            resp = client.get(ep, headers=auth_headers)
            if resp.status_code != 200:
                failures.append(f"{ep} -> {resp.status_code}")
        assert not failures, f"Endpoints not returning 200: {failures}"

    def test_health_returns_healthy(self, client):
        """Health endpoint must report healthy status."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("data", {}).get("status") == "healthy"

    def test_login_flow_works(self, client):
        """Login must succeed and return a valid token."""
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert len(body["access_token"]) > 20


# ---------------------------------------------------------------------------
# Step 10.5 — 灰度期间 P95 延迟 SLO
# ---------------------------------------------------------------------------

class TestCanaryLatencySLO:
    """P95 latency must be ≤ 500ms for core read APIs."""

    def _measure_p95(self, client, endpoint, headers, n=20):
        latencies = []
        for _ in range(n):
            t0 = time.perf_counter()
            resp = client.get(endpoint, headers=headers)
            latencies.append((time.perf_counter() - t0) * 1000)
            assert resp.status_code == 200, f"{endpoint} returned {resp.status_code}"
        latencies.sort()
        p95_idx = min(int(len(latencies) * 0.95), len(latencies) - 1)
        return latencies[p95_idx]

    def test_defense_events_p95(self, client, auth_headers):
        p95 = self._measure_p95(client, "/api/v1/defense/events", auth_headers)
        assert p95 <= 500, f"defense/events P95={p95:.0f}ms"

    def test_scan_assets_p95(self, client, auth_headers):
        p95 = self._measure_p95(client, "/api/v1/scan/assets", auth_headers)
        assert p95 <= 500, f"scan/assets P95={p95:.0f}ms"

    def test_ai_decisions_p95(self, client, auth_headers):
        p95 = self._measure_p95(client, "/api/v1/ai/decisions", auth_headers)
        assert p95 <= 500, f"ai/decisions P95={p95:.0f}ms"

    def test_overview_metrics_p95(self, client, auth_headers):
        p95 = self._measure_p95(client, "/api/v1/overview/metrics", auth_headers)
        assert p95 <= 500, f"overview/metrics P95={p95:.0f}ms"

    def test_health_p95(self, client, auth_headers):
        p95 = self._measure_p95(client, "/api/health", {})
        assert p95 <= 500, f"health P95={p95:.0f}ms"


# ---------------------------------------------------------------------------
# Step 10.7 — 上线后 SLO 验证
# ---------------------------------------------------------------------------

class TestPostLaunchSLO:
    """Post-launch SLO validation."""

    def test_no_5xx_on_core_endpoints(self, client, auth_headers):
        """No 500 errors on repeated requests to core endpoints."""
        endpoints = [
            "/api/health",
            "/api/v1/defense/events",
            "/api/v1/scan/assets",
            "/api/v1/ai/decisions",
            "/api/v1/overview/metrics",
            "/api/v1/overview/todos",
            "/api/v1/firewall/tasks",
        ]
        for ep in endpoints:
            for _ in range(10):
                resp = client.get(ep, headers=auth_headers)
                assert resp.status_code < 500, f"{ep} returned {resp.status_code}"

    def test_firewall_queue_not_stuck(self, client, auth_headers, db):
        """No excessive MANUAL_REQUIRED tasks (≤ 10)."""
        count = db.execute(
            text("SELECT COUNT(*) FROM firewall_sync_task WHERE state='MANUAL_REQUIRED'")
        ).fetchone()[0]
        assert count <= 10, f"MANUAL_REQUIRED tasks: {count} (max 10)"

    def test_audit_log_writable(self, db):
        """Audit log table is writable."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            text(
                "INSERT INTO audit_log (actor, action, target, result, trace_id, created_at) "
                "VALUES ('slo_check', 'slo_validation', 'system', 'success', 'slo_001', :now)"
            ),
            {"now": now},
        )
        db.commit()
        row = db.execute(
            text("SELECT COUNT(*) FROM audit_log WHERE trace_id='slo_001'")
        ).fetchone()
        assert row[0] >= 1

    def test_database_integrity(self, db):
        """SQLite integrity check passes."""
        result = db.execute(text("PRAGMA integrity_check")).fetchone()
        assert result[0] == "ok", f"DB integrity check failed: {result[0]}"

    def test_all_expected_tables_exist(self, db):
        """All core tables must exist."""
        expected = {
            "threat_event", "execution_task", "asset", "scan_task", "scan_finding",
            "device", "ai_decision_log", "ai_chat_session", "ai_chat_message",
            "user", "role", "permission", "role_permission", "user_role",
            "audit_log", "firewall_sync_task",
            "workflow_definition", "workflow_version", "workflow_run",
        }
        rows = db.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
        actual = {r[0] for r in rows}
        missing = expected - actual
        assert not missing, f"Missing tables: {sorted(missing)}"

    def test_rbac_data_intact(self, db):
        """RBAC base data (roles, permissions, admin user) must exist."""
        roles = db.execute(text("SELECT COUNT(*) FROM role")).fetchone()[0]
        assert roles >= 1, "No roles found"

        users = db.execute(text("SELECT COUNT(*) FROM user")).fetchone()[0]
        assert users >= 1, "No users found"

        perms = db.execute(text("SELECT COUNT(*) FROM permission")).fetchone()[0]
        assert perms >= 1, "No permissions found"

        admin = db.execute(
            text("SELECT COUNT(*) FROM user WHERE username='admin'")
        ).fetchone()[0]
        assert admin == 1, "Admin user missing"
