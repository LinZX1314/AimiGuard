"""
Step 10.2 — 压测（API、队列、扫描并发）并输出报告

验证：
  - API 并发请求下的响应延迟与成功率
  - 认证接口并发安全性
  - 防御/扫描/AI 接口并发读写
  - 队列并发提交（扫描任务）
  - P95 延迟 <= 500ms（不含长任务接口）
  - 错误率 <= 1%
"""
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class RequestResult:
    status_code: int
    latency_ms: float
    success: bool
    endpoint: str
    error: str = ""


@dataclass
class LoadTestReport:
    endpoint: str
    total_requests: int = 0
    success_count: int = 0
    error_count: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return (self.success_count / self.total_requests * 100) if self.total_requests else 0.0

    @property
    def p50_ms(self) -> float:
        return self._percentile(50)

    @property
    def p95_ms(self) -> float:
        return self._percentile(95)

    @property
    def p99_ms(self) -> float:
        return self._percentile(99)

    @property
    def avg_ms(self) -> float:
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0.0

    def _percentile(self, p: float) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_lat = sorted(self.latencies_ms)
        idx = int(len(sorted_lat) * p / 100)
        idx = min(idx, len(sorted_lat) - 1)
        return sorted_lat[idx]

    def summary(self) -> dict:
        return {
            "endpoint": self.endpoint,
            "total": self.total_requests,
            "success": self.success_count,
            "errors": self.error_count,
            "success_rate_pct": round(self.success_rate, 2),
            "avg_ms": round(self.avg_ms, 1),
            "p50_ms": round(self.p50_ms, 1),
            "p95_ms": round(self.p95_ms, 1),
            "p99_ms": round(self.p99_ms, 1),
        }


def run_load_test(
    client: TestClient,
    endpoint: str,
    method: str = "GET",
    headers: Optional[dict] = None,
    json_body: Optional[dict] = None,
    concurrency: int = 10,
    total_requests: int = 50,
) -> LoadTestReport:
    """Execute concurrent requests and collect metrics."""
    report = LoadTestReport(endpoint=endpoint)

    def _make_request(_i: int) -> RequestResult:
        t0 = time.perf_counter()
        try:
            if method == "GET":
                resp = client.get(endpoint, headers=headers)
            elif method == "POST":
                resp = client.post(endpoint, headers=headers, json=json_body)
            elif method == "PATCH":
                resp = client.patch(endpoint, headers=headers, json=json_body)
            else:
                resp = client.get(endpoint, headers=headers)
            latency = (time.perf_counter() - t0) * 1000
            ok = 200 <= resp.status_code < 500  # 4xx still "handled", not server error
            return RequestResult(
                status_code=resp.status_code,
                latency_ms=latency,
                success=ok,
                endpoint=endpoint,
                error="" if ok else f"HTTP {resp.status_code}",
            )
        except Exception as exc:
            latency = (time.perf_counter() - t0) * 1000
            return RequestResult(
                status_code=0,
                latency_ms=latency,
                success=False,
                endpoint=endpoint,
                error=str(exc),
            )

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(_make_request, i) for i in range(total_requests)]
        for f in as_completed(futures):
            result = f.result()
            report.total_requests += 1
            report.latencies_ms.append(result.latency_ms)
            if result.success:
                report.success_count += 1
            else:
                report.error_count += 1
                report.errors.append(result.error)

    return report


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def auth_headers(client):
    """Get admin auth headers."""
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    token = resp.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def load_reports():
    """Collect all load test reports for final summary."""
    reports = []
    yield reports
    # Print summary after all tests
    print("\n" + "=" * 70)
    print("  Step 10.2 压测汇总报告")
    print("=" * 70)
    for r in reports:
        s = r.summary()
        status = "✅" if s["success_rate_pct"] >= 99 and s["p95_ms"] <= 500 else "⚠️"
        print(
            f"  {status} {s['endpoint']:<40} "
            f"成功率={s['success_rate_pct']}%  "
            f"P95={s['p95_ms']}ms  "
            f"avg={s['avg_ms']}ms  "
            f"({s['total']}req)"
        )
    print("=" * 70)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

CONCURRENCY = 10
REQUESTS = 50


class TestAPILoadHealth:
    """Health and public endpoint load tests."""

    def test_health_concurrent(self, client, load_reports):
        report = run_load_test(client, "/api/health", concurrency=CONCURRENCY, total_requests=REQUESTS)
        load_reports.append(report)
        assert report.success_rate >= 99, f"Health success rate too low: {report.success_rate}%"
        assert report.p95_ms <= 500, f"Health P95 too high: {report.p95_ms}ms"

    def test_root_concurrent(self, client, load_reports):
        report = run_load_test(client, "/", concurrency=CONCURRENCY, total_requests=REQUESTS)
        load_reports.append(report)
        assert report.success_rate >= 99


class TestAPILoadAuth:
    """Authentication endpoint load tests."""

    def test_login_concurrent(self, client, load_reports):
        """Concurrent login requests."""
        report = run_load_test(
            client,
            "/api/v1/auth/login",
            method="POST",
            json_body={"username": "admin", "password": "admin123"},
            concurrency=5,
            total_requests=20,
        )
        load_reports.append(report)
        # Login may be rate-limited (429) — that's acceptable
        handled = report.success_count + sum(1 for e in report.errors if "429" in e)
        assert handled >= 15, f"Too many login failures: {report.error_count}"

    def test_login_wrong_password_concurrent(self, client, load_reports):
        """Concurrent login with wrong password should not crash."""
        report = run_load_test(
            client,
            "/api/v1/auth/login",
            method="POST",
            json_body={"username": "admin", "password": "wrong"},
            concurrency=5,
            total_requests=20,
        )
        load_reports.append(report)
        # All should return 401 or 429, none should be 500
        server_errors = sum(1 for e in report.errors if "500" in e or "502" in e)
        assert server_errors == 0, f"Server errors on bad login: {server_errors}"


class TestAPILoadDefense:
    """Defense chain load tests."""

    def test_defense_events_concurrent(self, client, auth_headers, load_reports):
        report = run_load_test(
            client,
            "/api/v1/defense/events",
            headers=auth_headers,
            concurrency=CONCURRENCY,
            total_requests=REQUESTS,
        )
        load_reports.append(report)
        assert report.success_rate >= 99, f"Defense events success rate: {report.success_rate}%"
        assert report.p95_ms <= 500, f"Defense events P95: {report.p95_ms}ms"

    def test_defense_pending_concurrent(self, client, auth_headers, load_reports):
        report = run_load_test(
            client,
            "/api/v1/defense/pending",
            headers=auth_headers,
            concurrency=CONCURRENCY,
            total_requests=REQUESTS,
        )
        load_reports.append(report)
        assert report.success_rate >= 99


class TestAPILoadScan:
    """Scan chain load tests."""

    def test_scan_assets_concurrent(self, client, auth_headers, load_reports):
        report = run_load_test(
            client,
            "/api/v1/scan/assets",
            headers=auth_headers,
            concurrency=CONCURRENCY,
            total_requests=REQUESTS,
        )
        load_reports.append(report)
        assert report.success_rate >= 99, f"Scan assets success rate: {report.success_rate}%"
        assert report.p95_ms <= 500

    def test_scan_tasks_concurrent(self, client, auth_headers, load_reports):
        report = run_load_test(
            client,
            "/api/v1/scan/tasks",
            headers=auth_headers,
            concurrency=CONCURRENCY,
            total_requests=REQUESTS,
        )
        load_reports.append(report)
        assert report.success_rate >= 99

    def test_scan_findings_concurrent(self, client, auth_headers, load_reports):
        report = run_load_test(
            client,
            "/api/v1/scan/findings",
            headers=auth_headers,
            concurrency=CONCURRENCY,
            total_requests=REQUESTS,
        )
        load_reports.append(report)
        assert report.success_rate >= 99


class TestAPILoadAI:
    """AI center load tests."""

    def test_ai_decisions_concurrent(self, client, auth_headers, load_reports):
        report = run_load_test(
            client,
            "/api/v1/ai/decisions",
            headers=auth_headers,
            concurrency=CONCURRENCY,
            total_requests=REQUESTS,
        )
        load_reports.append(report)
        assert report.success_rate >= 99, f"AI decisions success rate: {report.success_rate}%"
        assert report.p95_ms <= 500

    def test_ai_sessions_concurrent(self, client, auth_headers, load_reports):
        report = run_load_test(
            client,
            "/api/v1/ai/sessions",
            headers=auth_headers,
            concurrency=CONCURRENCY,
            total_requests=REQUESTS,
        )
        load_reports.append(report)
        assert report.success_rate >= 99


class TestAPILoadOverview:
    """Overview dashboard load tests."""

    def test_overview_stats_concurrent(self, client, auth_headers, load_reports):
        report = run_load_test(
            client,
            "/api/v1/overview/stats",
            headers=auth_headers,
            concurrency=CONCURRENCY,
            total_requests=REQUESTS,
        )
        load_reports.append(report)
        assert report.success_rate >= 99

    def test_overview_todos_concurrent(self, client, auth_headers, load_reports):
        report = run_load_test(
            client,
            "/api/v1/overview/todos",
            headers=auth_headers,
            concurrency=CONCURRENCY,
            total_requests=REQUESTS,
        )
        load_reports.append(report)
        assert report.success_rate >= 99


class TestAPILoadWorkflow:
    """Workflow API load tests."""

    def test_workflow_list_concurrent(self, client, auth_headers, load_reports):
        report = run_load_test(
            client,
            "/api/v1/workflows",
            headers=auth_headers,
            concurrency=CONCURRENCY,
            total_requests=REQUESTS,
        )
        load_reports.append(report)
        assert report.success_rate >= 99


class TestAPILoadAudit:
    """Audit log load tests."""

    def test_audit_logs_concurrent(self, client, auth_headers, load_reports):
        report = run_load_test(
            client,
            "/api/v1/audit/logs",
            headers=auth_headers,
            concurrency=CONCURRENCY,
            total_requests=REQUESTS,
        )
        load_reports.append(report)
        assert report.success_rate >= 99
        assert report.p95_ms <= 500


class TestConcurrentWriteOperations:
    """Test concurrent write operations for data integrity."""

    def test_concurrent_asset_creation(self, client, auth_headers, load_reports):
        """Concurrent asset creation should handle dedup correctly."""
        def _create_asset(i):
            t0 = time.perf_counter()
            resp = client.post(
                "/api/v1/scan/assets",
                headers=auth_headers,
                json={"target": f"192.168.100.{i}", "target_type": "IP", "description": f"load-test-{i}"},
            )
            latency = (time.perf_counter() - t0) * 1000
            ok = resp.status_code in (200, 201, 409)  # 409 = duplicate is acceptable
            return RequestResult(
                status_code=resp.status_code,
                latency_ms=latency,
                success=ok,
                endpoint="/api/v1/scan/assets [POST]",
                error="" if ok else f"HTTP {resp.status_code}",
            )

        report = LoadTestReport(endpoint="/api/v1/scan/assets [POST concurrent]")
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(_create_asset, i) for i in range(20)]
            for f in as_completed(futures):
                result = f.result()
                report.total_requests += 1
                report.latencies_ms.append(result.latency_ms)
                if result.success:
                    report.success_count += 1
                else:
                    report.error_count += 1
                    report.errors.append(result.error)

        load_reports.append(report)
        assert report.success_rate >= 95, f"Asset creation success rate: {report.success_rate}%"


class TestSLOCompliance:
    """Verify SLO targets from README."""

    def test_p95_api_latency_under_500ms(self, client, auth_headers):
        """README SLO: P95 API latency <= 500ms (excluding long tasks)."""
        endpoints = [
            "/api/health",
            "/api/v1/defense/events",
            "/api/v1/scan/assets",
            "/api/v1/ai/decisions",
            "/api/v1/overview/stats",
        ]
        for ep in endpoints:
            report = run_load_test(client, ep, headers=auth_headers, concurrency=5, total_requests=20)
            assert report.p95_ms <= 500, f"{ep} P95 = {report.p95_ms}ms exceeds 500ms SLO"

    def test_no_5xx_under_normal_load(self, client, auth_headers):
        """No 500 errors under normal concurrent load."""
        endpoints = [
            "/api/health",
            "/api/v1/defense/events",
            "/api/v1/scan/tasks",
            "/api/v1/overview/todos",
        ]
        for ep in endpoints:
            report = run_load_test(client, ep, headers=auth_headers, concurrency=10, total_requests=30)
            server_errors = sum(1 for e in report.errors if "500" in e)
            assert server_errors == 0, f"{ep} had {server_errors} server errors"
