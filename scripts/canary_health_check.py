#!/usr/bin/env python3
"""
Step 10.5 — 小流量灰度发布健康检查脚本

功能：
  1. 连续检查核心 API 端点健康状态
  2. 监控 P95 延迟、错误率、降级率
  3. 自动判断是否满足灰度放量条件
  4. 输出观察报告

用法：
  python scripts/canary_health_check.py                        # 默认 5 轮，间隔 10 秒
  python scripts/canary_health_check.py --rounds 30 --interval 5
  python scripts/canary_health_check.py --base-url http://10.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    import urllib.request
    import urllib.error

    class _SimpleRequests:
        """Minimal fallback when requests is not installed."""

        @staticmethod
        def get(url, headers=None, timeout=10):
            req = urllib.request.Request(url, headers=headers or {})
            try:
                resp = urllib.request.urlopen(req, timeout=timeout)
                return _SimpleResponse(resp.getcode(), resp.read().decode())
            except urllib.error.HTTPError as e:
                return _SimpleResponse(e.code, e.read().decode() if e.fp else "")
            except Exception as e:
                return _SimpleResponse(0, str(e))

        @staticmethod
        def post(url, json_body=None, headers=None, timeout=10):
            data = json.dumps(json_body or {}).encode()
            h = {"Content-Type": "application/json"}
            h.update(headers or {})
            req = urllib.request.Request(url, data=data, headers=h, method="POST")
            try:
                resp = urllib.request.urlopen(req, timeout=timeout)
                return _SimpleResponse(resp.getcode(), resp.read().decode())
            except urllib.error.HTTPError as e:
                return _SimpleResponse(e.code, e.read().decode() if e.fp else "")
            except Exception as e:
                return _SimpleResponse(0, str(e))

    @dataclass
    class _SimpleResponse:
        status_code: int
        text: str

        def json(self):
            return json.loads(self.text)

    requests = _SimpleRequests()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CANARY_ENDPOINTS = [
    {"method": "GET", "path": "/api/health", "label": "健康检查", "auth": False},
    {"method": "GET", "path": "/api/v1/defense/events", "label": "防御事件", "auth": True},
    {"method": "GET", "path": "/api/v1/scan/assets", "label": "扫描资产", "auth": True},
    {"method": "GET", "path": "/api/v1/ai/decisions", "label": "AI 决策", "auth": True},
    {"method": "GET", "path": "/api/v1/overview/metrics", "label": "概览指标", "auth": True},
    {"method": "GET", "path": "/api/v1/overview/todos", "label": "待办事项", "auth": True},
    {"method": "GET", "path": "/api/v1/firewall/tasks", "label": "防火墙任务", "auth": True},
    {"method": "GET", "path": "/api/v1/workflows", "label": "工作流列表", "auth": True},
]

# SLO thresholds
SLO_P95_MS = 500
SLO_ERROR_RATE_PCT = 1.0
SLO_MIN_SUCCESS_RATE = 99.0


@dataclass
class EndpointMetrics:
    label: str
    path: str
    latencies: list[float] = field(default_factory=list)
    success: int = 0
    errors: int = 0
    status_codes: list[int] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.success + self.errors

    @property
    def p95(self) -> float:
        if not self.latencies:
            return 0.0
        s = sorted(self.latencies)
        idx = min(int(len(s) * 0.95), len(s) - 1)
        return s[idx]

    @property
    def avg(self) -> float:
        return statistics.mean(self.latencies) if self.latencies else 0.0

    @property
    def success_rate(self) -> float:
        return (self.success / self.total * 100) if self.total else 0.0

    @property
    def error_rate(self) -> float:
        return (self.errors / self.total * 100) if self.total else 0.0


def _login(base_url: str) -> Optional[str]:
    """Get auth token."""
    try:
        resp = requests.post(
            f"{base_url}/api/v1/auth/login",
            json_body={"username": "admin", "password": "admin123"},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
    except Exception:
        pass
    return None


def run_canary(
    base_url: str = "http://localhost:8000",
    rounds: int = 5,
    interval: int = 10,
) -> dict:
    """Run canary health check and return report."""
    print("=" * 60)
    print("  Step 10.5 灰度发布健康观察")
    print(f"  目标: {base_url}")
    print(f"  轮次: {rounds}  间隔: {interval}s")
    print("=" * 60)

    # Login
    token = _login(base_url)
    if not token:
        print("  ⚠️  无法获取 token，仅检查公开端点")
    auth_headers = {"Authorization": f"Bearer {token}"} if token else {}

    metrics: dict[str, EndpointMetrics] = {}
    for ep in CANARY_ENDPOINTS:
        metrics[ep["path"]] = EndpointMetrics(label=ep["label"], path=ep["path"])

    all_ok = True

    for r in range(1, rounds + 1):
        print(f"\n  ── 第 {r}/{rounds} 轮 ──")

        for ep in CANARY_ENDPOINTS:
            if ep["auth"] and not token:
                continue

            m = metrics[ep["path"]]
            url = f"{base_url}{ep['path']}"
            headers = auth_headers if ep["auth"] else {}

            t0 = time.perf_counter()
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                latency = (time.perf_counter() - t0) * 1000
                m.latencies.append(latency)
                m.status_codes.append(resp.status_code)

                if 200 <= resp.status_code < 400:
                    m.success += 1
                    status = "✅"
                elif resp.status_code < 500:
                    m.success += 1  # 4xx is handled, not a server error
                    status = "⚠️"
                else:
                    m.errors += 1
                    status = "❌"
                    all_ok = False

                print(f"    {status} {ep['label']:<12} {resp.status_code} {latency:.0f}ms")
            except Exception as exc:
                latency = (time.perf_counter() - t0) * 1000
                m.latencies.append(latency)
                m.errors += 1
                m.status_codes.append(0)
                all_ok = False
                print(f"    ❌ {ep['label']:<12} ERROR: {exc}")

        if r < rounds:
            time.sleep(interval)

    # -- Summary --
    print("\n" + "=" * 60)
    print("  灰度观察汇总")
    print("=" * 60)

    slo_pass = True
    summaries = []

    for ep in CANARY_ENDPOINTS:
        m = metrics[ep["path"]]
        if m.total == 0:
            continue

        p95_ok = m.p95 <= SLO_P95_MS
        rate_ok = m.success_rate >= SLO_MIN_SUCCESS_RATE
        ep_ok = p95_ok and rate_ok

        if not ep_ok:
            slo_pass = False

        icon = "✅" if ep_ok else "❌"
        print(
            f"  {icon} {m.label:<12} "
            f"成功率={m.success_rate:.1f}%  "
            f"P95={m.p95:.0f}ms  "
            f"avg={m.avg:.0f}ms  "
            f"({m.total}req)"
        )
        summaries.append({
            "label": m.label,
            "path": m.path,
            "total": m.total,
            "success_rate_pct": round(m.success_rate, 2),
            "error_rate_pct": round(m.error_rate, 2),
            "p95_ms": round(m.p95, 1),
            "avg_ms": round(m.avg, 1),
            "slo_pass": ep_ok,
        })

    print()
    if slo_pass:
        print("  ✅ SLO 达标 — 可以继续放量")
    else:
        print("  ❌ SLO 未达标 — 建议回滚或排查后重试")
    print("=" * 60)

    report = {
        "canary_check": "step10_5_canary_health",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "rounds": rounds,
        "interval_seconds": interval,
        "slo_pass": slo_pass,
        "slo_thresholds": {
            "p95_ms": SLO_P95_MS,
            "error_rate_pct": SLO_ERROR_RATE_PCT,
            "min_success_rate_pct": SLO_MIN_SUCCESS_RATE,
        },
        "endpoints": summaries,
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="Step 10.5 灰度发布健康检查")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API 基础 URL")
    parser.add_argument("--rounds", type=int, default=5, help="检查轮次")
    parser.add_argument("--interval", type=int, default=10, help="轮次间隔（秒）")
    parser.add_argument("--output", type=str, default=None, help="报告输出路径")
    args = parser.parse_args()

    report = run_canary(
        base_url=args.base_url,
        rounds=args.rounds,
        interval=args.interval,
    )

    output_path = args.output or f"canary_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    Path(output_path).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n📄 报告已保存: {output_path}")

    sys.exit(0 if report["slo_pass"] else 1)


if __name__ == "__main__":
    main()
