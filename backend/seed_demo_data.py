#!/usr/bin/env python3
"""Seed demo data for dashboards and end-to-end showcase."""

from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from core.database import (
    AIChatMessage,
    AIChatSession,
    AIReport,
    AITTSTask,
    Asset,
    AuditLog,
    CollectorConfig,
    Device,
    ExecutionTask,
    init_db,
    ScanFinding,
    ScanTask,
    SessionLocal,
    ThreatEvent,
    User,
)

DEMO_TRACE_PREFIX = "demo_"
DEMO_TAG = "aimiguard-demo"
DEMO_OPERATOR = "demo-bot"
DEMO_DEVICE_NAME = "DEMO-CORE-SWITCH"
SCAN_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "scan_outputs" / "demo"
REPORT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "scan_outputs" / "reports"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _trace_id(name: str) -> str:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    return f"{DEMO_TRACE_PREFIX}{digest}"


def _write_demo_artifacts() -> dict[str, str]:
    SCAN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    scan_files = {
        "web": SCAN_OUTPUT_DIR / "nmap_demo_web.xml",
        "vpn": SCAN_OUTPUT_DIR / "nmap_demo_vpn.xml",
    }
    report_files = {
        "daily": REPORT_OUTPUT_DIR / "demo_daily_report.md",
        "weekly": REPORT_OUTPUT_DIR / "demo_weekly_report.md",
    }

    scan_files["web"].write_text(
        """<nmaprun><host><status state="up"/><ports><port protocol="tcp" portid="443"><state state="open"/><service name="https" product="nginx" version="1.18.0"/></port></ports></host></nmaprun>""",
        encoding="utf-8",
    )
    scan_files["vpn"].write_text(
        """<nmaprun><host><status state="up"/><ports><port protocol="tcp" portid="1194"><state state="open"/><service name="openvpn" product="OpenVPN" version="2.4"/></port></ports></host></nmaprun>""",
        encoding="utf-8",
    )

    report_files["daily"].write_text(
        "# Demo Daily Report\n\n- Defense incidents increased in the DMZ.\n- Two high-risk findings require patching.\n",
        encoding="utf-8",
    )
    report_files["weekly"].write_text(
        "# Demo Weekly Report\n\n- Attack activity focused on SSH, RDP, and web services.\n- Probe coverage includes DMZ, VPN, and legacy hosts.\n",
        encoding="utf-8",
    )

    return {
        "scan_web": str(scan_files["web"]),
        "scan_vpn": str(scan_files["vpn"]),
        "report_daily": str(report_files["daily"]),
        "report_weekly": str(report_files["weekly"]),
    }


def _ensure_demo_user(db) -> User:
    user = db.query(User).filter(User.username == "admin").first()
    if user:
        return user

    user = db.query(User).order_by(User.id.asc()).first()
    if user:
        return user

    password_hash = hashlib.sha256("admin123".encode("utf-8")).hexdigest()
    user = User(
        username="admin",
        password_hash=password_hash,
        email="admin@aimiguan.local",
        full_name="Demo Admin",
        enabled=1,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    db.add(user)
    db.flush()
    return user


def _ensure_demo_device(db) -> Device:
    device = db.query(Device).filter(Device.name == DEMO_DEVICE_NAME).first()
    if device:
        return device

    device = Device(
        name=DEMO_DEVICE_NAME,
        ip="10.0.0.254",
        port=23,
        vendor="generic",
        device_type="switch",
        enabled=1,
        description="[demo] core switch for execution demo",
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    db.add(device)
    db.flush()
    return device


def _ensure_demo_collector_configs(db) -> None:
    demo_configs = [
        ("hfish", "enabled", "true", "[demo] enable HFish collector"),
        ("hfish", "host_port", "demo-hfish.local:4433", "[demo] HFish endpoint"),
        ("hfish", "sync_interval", "60", "[demo] HFish sync interval"),
        ("nmap", "enabled", "true", "[demo] enable Nmap collector"),
        ("nmap", "nmap_path", "nmap", "[demo] Nmap binary"),
        ("nmap", "ip_ranges", '["10.0.10.0/24","172.16.3.45"]', "[demo] Nmap targets"),
        ("nmap", "scan_interval", "86400", "[demo] Nmap scan interval"),
    ]

    for collector_type, config_key, config_value, description in demo_configs:
        existing = (
            db.query(CollectorConfig)
            .filter(
                CollectorConfig.collector_type == collector_type,
                CollectorConfig.config_key == config_key,
            )
            .first()
        )
        if existing:
            continue
        db.add(
            CollectorConfig(
                collector_type=collector_type,
                config_key=config_key,
                config_value=config_value,
                is_sensitive=0,
                enabled=1,
                description=description,
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
        )


def clear_demo_data(db) -> None:
    demo_sessions = (
        db.query(AIChatSession.id)
        .filter(AIChatSession.operator == DEMO_OPERATOR)
        .all()
    )
    demo_session_ids = [row[0] for row in demo_sessions]
    if demo_session_ids:
        db.query(AIChatMessage).filter(AIChatMessage.session_id.in_(demo_session_ids)).delete(
            synchronize_session=False
        )
        db.query(AIChatSession).filter(AIChatSession.id.in_(demo_session_ids)).delete(
            synchronize_session=False
        )

    demo_task_ids = [
        row[0]
        for row in db.query(ScanTask.id)
        .filter(ScanTask.trace_id.like(f"{DEMO_TRACE_PREFIX}%"))
        .all()
    ]
    if demo_task_ids:
        db.query(ScanFinding).filter(ScanFinding.scan_task_id.in_(demo_task_ids)).delete(
            synchronize_session=False
        )
        db.query(ScanTask).filter(ScanTask.id.in_(demo_task_ids)).delete(
            synchronize_session=False
        )

    demo_event_ids = [
        row[0]
        for row in db.query(ThreatEvent.id)
        .filter(ThreatEvent.trace_id.like(f"{DEMO_TRACE_PREFIX}%"))
        .all()
    ]
    if demo_event_ids:
        db.query(ExecutionTask).filter(ExecutionTask.event_id.in_(demo_event_ids)).delete(
            synchronize_session=False
        )
        db.query(ThreatEvent).filter(ThreatEvent.id.in_(demo_event_ids)).delete(
            synchronize_session=False
        )

    db.query(AIReport).filter(AIReport.trace_id.like(f"{DEMO_TRACE_PREFIX}%")).delete(
        synchronize_session=False
    )
    db.query(AITTSTask).filter(AITTSTask.trace_id.like(f"{DEMO_TRACE_PREFIX}%")).delete(
        synchronize_session=False
    )
    db.query(AuditLog).filter(AuditLog.trace_id.like(f"{DEMO_TRACE_PREFIX}%")).delete(
        synchronize_session=False
    )
    db.query(Asset).filter(Asset.tags.like(f"%{DEMO_TAG}%")).delete(synchronize_session=False)
    db.query(Device).filter(Device.name == DEMO_DEVICE_NAME).delete(synchronize_session=False)
    db.commit()


def seed_demo_data(db) -> dict[str, Any]:
    clear_demo_data(db)

    artifacts = _write_demo_artifacts()
    user = _ensure_demo_user(db)
    device = _ensure_demo_device(db)
    _ensure_demo_collector_configs(db)

    now = _utc_now()

    assets = [
        Asset(
            target="10.0.10.21",
            target_type="IP",
            tags=f"{DEMO_TAG},dmz,web",
            priority=9,
            enabled=1,
            description="[demo] DMZ web gateway",
            created_at=now - timedelta(days=12),
            updated_at=now - timedelta(hours=2),
        ),
        Asset(
            target="10.0.20.8",
            target_type="IP",
            tags=f"{DEMO_TAG},legacy,windows",
            priority=8,
            enabled=1,
            description="[demo] legacy Windows host",
            created_at=now - timedelta(days=9),
            updated_at=now - timedelta(days=1),
        ),
        Asset(
            target="172.16.3.45",
            target_type="IP",
            tags=f"{DEMO_TAG},vpn,edge",
            priority=7,
            enabled=1,
            description="[demo] VPN edge node",
            created_at=now - timedelta(days=7),
            updated_at=now - timedelta(hours=8),
        ),
        Asset(
            target="10.0.30.0/24",
            target_type="CIDR",
            tags=f"{DEMO_TAG},segment,office",
            priority=5,
            enabled=0,
            description="[demo] office network segment",
            created_at=now - timedelta(days=6),
            updated_at=now - timedelta(days=2),
        ),
    ]
    db.add_all(assets)
    db.flush()

    threat_events = [
        ThreatEvent(
            ip="203.0.113.45",
            source="hfish",
            source_vendor="hfish",
            source_type="attack_source",
            source_event_id="demo-event-001",
            attack_count=18,
            asset_ip="10.0.10.21",
            service_name="ssh",
            service_type="tcp",
            ai_score=92,
            ai_reason="Repeated SSH brute-force attempts from a new source.",
            action_suggest="BLOCK",
            status="PENDING",
            trace_id=_trace_id("threat-event-001"),
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(minutes=50),
        ),
        ThreatEvent(
            ip="198.51.100.77",
            source="hfish",
            source_vendor="hfish",
            source_type="attack_source",
            source_event_id="demo-event-002",
            attack_count=11,
            asset_ip="172.16.3.45",
            service_name="vpn",
            service_type="udp",
            ai_score=88,
            ai_reason="Credential stuffing detected on VPN access.",
            action_suggest="BLOCK",
            status="DONE",
            trace_id=_trace_id("threat-event-002"),
            created_at=now - timedelta(hours=4),
            updated_at=now - timedelta(hours=3),
        ),
        ThreatEvent(
            ip="45.67.89.10",
            source="hfish",
            source_vendor="hfish",
            source_type="attack_detail",
            source_event_id="demo-event-003",
            attack_count=4,
            asset_ip="10.0.20.8",
            service_name="rdp",
            service_type="tcp",
            ai_score=74,
            ai_reason="RDP probing observed, but no successful execution evidence.",
            action_suggest="MONITOR",
            status="PENDING",
            trace_id=_trace_id("threat-event-003"),
            created_at=now - timedelta(hours=22),
            updated_at=now - timedelta(hours=20),
        ),
        ThreatEvent(
            ip="91.203.12.44",
            source="hfish",
            source_vendor="hfish",
            source_type="attack_source",
            source_event_id="demo-event-004",
            attack_count=6,
            asset_ip="10.0.20.8",
            service_name="smb",
            service_type="tcp",
            ai_score=58,
            ai_reason="Lateral movement indicators were incomplete and required review.",
            action_suggest="MONITOR",
            status="REJECTED",
            trace_id=_trace_id("threat-event-004"),
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2, hours=-1),
        ),
        ThreatEvent(
            ip="185.193.88.21",
            source="hfish",
            source_vendor="hfish",
            source_type="attack_detail",
            source_event_id="demo-event-005",
            attack_count=23,
            asset_ip="10.0.10.21",
            service_name="http",
            service_type="tcp",
            ai_score=96,
            ai_reason="Exploit pattern matched against public CVE indicators.",
            action_suggest="BLOCK",
            status="FAILED",
            trace_id=_trace_id("threat-event-005"),
            created_at=now - timedelta(days=3),
            updated_at=now - timedelta(days=3, hours=-2),
        ),
    ]
    db.add_all(threat_events)
    db.flush()

    execution_tasks = [
        ExecutionTask(
            event_id=threat_events[1].id,
            device_id=device.id,
            action="BLOCK",
            state="SUCCESS",
            retry_count=0,
            trace_id=_trace_id("exec-task-001"),
            created_at=now - timedelta(hours=4),
            started_at=now - timedelta(hours=4),
            ended_at=now - timedelta(hours=3, minutes=40),
            updated_at=now - timedelta(hours=3, minutes=40),
        ),
        ExecutionTask(
            event_id=threat_events[4].id,
            device_id=device.id,
            action="BLOCK",
            state="MANUAL_REQUIRED",
            retry_count=3,
            error_message="Upstream device rejected ACL update after retries.",
            trace_id=_trace_id("exec-task-002"),
            created_at=now - timedelta(days=3),
            started_at=now - timedelta(days=3),
            ended_at=now - timedelta(days=3, minutes=-25),
            updated_at=now - timedelta(hours=10),
        ),
        ExecutionTask(
            event_id=threat_events[2].id,
            device_id=device.id,
            action="MONITOR",
            state="FAILED",
            retry_count=1,
            error_message="Execution queue timeout.",
            trace_id=_trace_id("exec-task-003"),
            created_at=now - timedelta(hours=22),
            started_at=now - timedelta(hours=22),
            ended_at=now - timedelta(hours=21, minutes=35),
            updated_at=now - timedelta(hours=21, minutes=35),
        ),
    ]
    db.add_all(execution_tasks)
    db.flush()

    scan_tasks = [
        ScanTask(
            asset_id=assets[0].id,
            target=assets[0].target,
            target_type=assets[0].target_type,
            tool_name="nmap",
            profile="deep",
            script_set="web",
            state="REPORTED",
            priority=9,
            timeout_seconds=1800,
            raw_output_path=artifacts["scan_web"],
            trace_id=_trace_id("scan-task-001"),
            created_at=now - timedelta(hours=6),
            started_at=now - timedelta(hours=6),
            ended_at=now - timedelta(hours=5, minutes=42),
            updated_at=now - timedelta(hours=5, minutes=42),
        ),
        ScanTask(
            asset_id=assets[1].id,
            target=assets[1].target,
            target_type=assets[1].target_type,
            tool_name="nmap",
            profile="baseline",
            script_set="legacy",
            state="FAILED",
            priority=8,
            timeout_seconds=1200,
            raw_output_path=None,
            error_message="Target timeout after 1200 seconds.",
            trace_id=_trace_id("scan-task-002"),
            created_at=now - timedelta(days=1, hours=2),
            started_at=now - timedelta(days=1, hours=2),
            ended_at=now - timedelta(days=1, hours=1, minutes=30),
            updated_at=now - timedelta(days=1, hours=1, minutes=30),
        ),
        ScanTask(
            asset_id=assets[2].id,
            target=assets[2].target,
            target_type=assets[2].target_type,
            tool_name="nmap",
            profile="fast",
            script_set="vpn",
            state="RUNNING",
            priority=7,
            timeout_seconds=900,
            raw_output_path=artifacts["scan_vpn"],
            trace_id=_trace_id("scan-task-003"),
            created_at=now - timedelta(minutes=35),
            started_at=now - timedelta(minutes=30),
            updated_at=now - timedelta(minutes=2),
        ),
        ScanTask(
            asset_id=assets[0].id,
            target=assets[0].target,
            target_type=assets[0].target_type,
            tool_name="nmap",
            profile="baseline",
            script_set="edge",
            state="REPORTED",
            priority=8,
            timeout_seconds=1800,
            raw_output_path=artifacts["scan_vpn"],
            trace_id=_trace_id("scan-task-004"),
            created_at=now - timedelta(days=3, hours=5),
            started_at=now - timedelta(days=3, hours=5),
            ended_at=now - timedelta(days=3, hours=4, minutes=34),
            updated_at=now - timedelta(days=3, hours=4, minutes=34),
        ),
        ScanTask(
            asset_id=assets[3].id,
            target=assets[3].target,
            target_type=assets[3].target_type,
            tool_name="nmap",
            profile="baseline",
            script_set="segment",
            state="CREATED",
            priority=5,
            timeout_seconds=1800,
            trace_id=_trace_id("scan-task-005"),
            created_at=now - timedelta(minutes=12),
            updated_at=now - timedelta(minutes=12),
        ),
    ]
    db.add_all(scan_tasks)
    db.flush()

    scan_findings = [
        ScanFinding(
            scan_task_id=scan_tasks[0].id,
            asset=assets[0].target,
            port=443,
            service="https",
            vuln_id="demo-vuln-001",
            cve="CVE-2023-25690",
            severity="HIGH",
            evidence="nginx 1.18.0 with outdated mod_proxy exposure.",
            status="NEW",
            hostname="dmz-web-01",
            os_type="Linux",
            trace_id=_trace_id("scan-finding-001"),
            created_at=now - timedelta(hours=5, minutes=40),
            updated_at=now - timedelta(hours=5, minutes=40),
        ),
        ScanFinding(
            scan_task_id=scan_tasks[0].id,
            asset=assets[0].target,
            port=22,
            service="ssh",
            vuln_id="demo-vuln-002",
            cve="CVE-2018-15473",
            severity="MEDIUM",
            evidence="OpenSSH user enumeration pattern detected.",
            status="NEW",
            hostname="dmz-web-01",
            os_type="Linux",
            trace_id=_trace_id("scan-finding-002"),
            created_at=now - timedelta(hours=5, minutes=39),
            updated_at=now - timedelta(hours=5, minutes=39),
        ),
        ScanFinding(
            scan_task_id=scan_tasks[0].id,
            asset=assets[0].target,
            port=80,
            service="http",
            vuln_id="demo-vuln-003",
            severity="LOW",
            evidence="Missing redirect from HTTP to HTTPS.",
            status="NEW",
            hostname="dmz-web-01",
            os_type="Linux",
            trace_id=_trace_id("scan-finding-003"),
            created_at=now - timedelta(hours=5, minutes=38),
            updated_at=now - timedelta(hours=5, minutes=38),
        ),
        ScanFinding(
            scan_task_id=scan_tasks[3].id,
            asset=assets[0].target,
            port=3389,
            service="rdp",
            vuln_id="demo-vuln-004",
            cve="CVE-2019-0708",
            severity="HIGH",
            evidence="Legacy RDP exposure discovered in hybrid edge subnet.",
            status="CONFIRMED",
            hostname="dmz-edge-legacy",
            os_type="Windows",
            trace_id=_trace_id("scan-finding-004"),
            created_at=now - timedelta(days=3, hours=4, minutes=20),
            updated_at=now - timedelta(days=3, hours=4, minutes=10),
        ),
        ScanFinding(
            scan_task_id=scan_tasks[3].id,
            asset=assets[2].target,
            port=1194,
            service="openvpn",
            vuln_id="demo-vuln-005",
            severity="INFO",
            evidence="OpenVPN endpoint fingerprinted successfully.",
            status="NEW",
            hostname="vpn-edge-01",
            os_type="Linux",
            trace_id=_trace_id("scan-finding-005"),
            created_at=now - timedelta(days=3, hours=4, minutes=18),
            updated_at=now - timedelta(days=3, hours=4, minutes=18),
        ),
    ]
    db.add_all(scan_findings)
    db.flush()

    session = AIChatSession(
        user_id=user.id,
        context_type="general",
        context_id=None,
        operator=DEMO_OPERATOR,
        started_at=now - timedelta(minutes=40),
        expires_at=None,
        created_at=now - timedelta(minutes=40),
    )
    db.add(session)
    db.flush()

    db.add_all(
        [
            AIChatMessage(
                session_id=session.id,
                role="user",
                content="总结一下目前最需要优先处理的风险。",
                created_at=now - timedelta(minutes=39),
            ),
            AIChatMessage(
                session_id=session.id,
                role="assistant",
                content="优先处理 DMZ Web 主机的高危漏洞和需要人工介入的封禁任务。",
                created_at=now - timedelta(minutes=38),
            ),
            AIChatMessage(
                session_id=session.id,
                role="assistant",
                content="建议先修复 CVE-2023-25690，再排查 ACL 执行失败原因。",
                created_at=now - timedelta(minutes=37),
            ),
        ]
    )

    db.add_all(
        [
            AIReport(
                report_type="daily",
                scope="全局",
                summary="日报：DMZ 区域告警升高，存在 2 条高危扫描发现和 1 条人工介入任务。",
                detail_path=artifacts["report_daily"],
                trace_id=_trace_id("report-daily"),
                created_at=now - timedelta(hours=2),
            ),
            AIReport(
                report_type="weekly",
                scope="全局",
                summary="周报：攻击活动集中在 SSH、RDP 与 Web 入口，建议优先加固 DMZ 与 VPN 边界。",
                detail_path=artifacts["report_weekly"],
                trace_id=_trace_id("report-weekly"),
                created_at=now - timedelta(days=1),
            ),
        ]
    )

    db.add_all(
        [
            AITTSTask(
                source_type="report",
                source_id=1,
                text_content="Aimiguan demo daily summary.",
                voice_model="local-tts-v1",
                audio_path=None,
                state="PENDING",
                trace_id=_trace_id("tts-pending"),
                created_at=now - timedelta(minutes=25),
                updated_at=now - timedelta(minutes=25),
            ),
            AITTSTask(
                source_type="message",
                source_id=session.id,
                text_content="Manual intervention is still required for one execution task.",
                voice_model="local-tts-v1",
                audio_path=None,
                state="FAILED",
                error_message="Demo engine offline.",
                trace_id=_trace_id("tts-failed"),
                created_at=now - timedelta(hours=3),
                updated_at=now - timedelta(hours=3),
            ),
        ]
    )

    db.add_all(
        [
            AuditLog(
                actor=DEMO_OPERATOR,
                action="demo_seed",
                target="dashboard_demo",
                target_type="seed",
                reason="Initial demo dataset import",
                result="success",
                trace_id=_trace_id("audit-seed"),
                created_at=now - timedelta(minutes=10),
            ),
            AuditLog(
                actor="operator",
                action="approve_event",
                target=str(threat_events[1].id),
                target_type="threat_event",
                target_ip=threat_events[1].ip,
                reason="AI score exceeded auto-review threshold",
                result="success",
                trace_id=_trace_id("audit-approve"),
                created_at=now - timedelta(hours=3, minutes=50),
            ),
            AuditLog(
                actor="scheduler",
                action="nmap_auto_scan",
                target=assets[0].target,
                target_type="scan_task",
                result="success",
                trace_id=_trace_id("audit-scan"),
                created_at=now - timedelta(hours=6),
            ),
        ]
    )

    db.commit()

    return {
        "assets": len(assets),
        "threat_events": len(threat_events),
        "execution_tasks": len(execution_tasks),
        "scan_tasks": len(scan_tasks),
        "scan_findings": len(scan_findings),
        "reports": 2,
        "tts_tasks": 2,
        "audit_logs": 3,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Aimiguan demo data")
    parser.add_argument(
        "--reset-only",
        action="store_true",
        help="Remove existing demo data without inserting a new dataset",
    )
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        if args.reset_only:
            clear_demo_data(db)
            print("Demo data cleared.")
            return

        summary = seed_demo_data(db)
        print("Demo data seeded successfully.")
        for key, value in summary.items():
            print(f"- {key}: {value}")
        print("Use `python backend/seed_demo_data.py --reset-only` to remove demo data.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
