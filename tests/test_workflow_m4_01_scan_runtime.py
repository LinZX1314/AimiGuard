from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from core.database import AIReport, Asset, ScanFinding, ScanTask, WorkflowRun, WorkflowStepRun
from services import workflow_runtime as workflow_runtime_module
from services.workflow_runtime import run_published_workflow


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _scan_workflow_dsl(workflow_key: str) -> dict:
    return {
        "schema_version": "1.0.0",
        "workflow_id": workflow_key,
        "version": 1,
        "name": f"Scan Workflow {workflow_key}",
        "description": "scan runtime workflow",
        "status": "DRAFT",
        "context": {
            "inputs": {"asset_id": {"type": "integer"}},
            "outputs": {"report_id": None},
            "trace_id": "{{ trace_id }}",
        },
        "runtime": {
            "initial_state": "QUEUED",
            "terminal_states": ["SUCCESS", "FAILED", "MANUAL_REQUIRED", "CANCELLED"],
            "state_enum": ["QUEUED", "RUNNING", "RETRYING", "SUCCESS", "FAILED", "MANUAL_REQUIRED", "CANCELLED"],
        },
        "nodes": [
            {
                "id": "trigger_scan",
                "type": "trigger",
                "name": "Trigger Scan",
                "config": {"source_type": "manual_scan"},
                "timeout": 10,
                "retry_policy": {"max_retries": 0, "backoff_seconds": 1, "backoff_multiplier": 1.0, "retry_on": []},
            },
            {
                "id": "select_asset",
                "type": "scan_asset_select",
                "name": "Select Asset",
                "config": {"service": "scan.select_asset"},
                "timeout": 10,
                "retry_policy": {"max_retries": 0, "backoff_seconds": 1, "backoff_multiplier": 1.0, "retry_on": []},
            },
            {
                "id": "create_task",
                "type": "scan_task_create",
                "name": "Create Scan Task",
                "config": {"service": "scan.create_task", "profile": "default", "tool_name": "nmap", "timeout_seconds": 180},
                "timeout": 30,
                "retry_policy": {"max_retries": 0, "backoff_seconds": 1, "backoff_multiplier": 1.0, "retry_on": []},
            },
            {
                "id": "parse_result",
                "type": "scan_result_parse",
                "name": "Run And Parse Scan",
                "config": {"service": "scan.run_task"},
                "timeout": 120,
                "retry_policy": {"max_retries": 0, "backoff_seconds": 1, "backoff_multiplier": 1.0, "retry_on": []},
            },
            {
                "id": "generate_report",
                "type": "scan_report",
                "name": "Generate Scan Report",
                "config": {"service": "scan.generate_report", "report_type": "scan"},
                "timeout": 60,
                "retry_policy": {"max_retries": 0, "backoff_seconds": 1, "backoff_multiplier": 1.0, "retry_on": []},
            },
            {
                "id": "audit_log",
                "type": "audit",
                "name": "Audit Scan Workflow",
                "config": {"service": "audit_service.log"},
                "timeout": 10,
                "retry_policy": {"max_retries": 0, "backoff_seconds": 1, "backoff_multiplier": 1.0, "retry_on": []},
            },
        ],
        "edges": [
            {"from": "trigger_scan", "to": "select_asset", "condition": "true", "priority": 100},
            {"from": "select_asset", "to": "create_task", "condition": "true", "priority": 100},
            {"from": "create_task", "to": "parse_result", "condition": "true", "priority": 100},
            {"from": "parse_result", "to": "generate_report", "condition": "true", "priority": 100},
            {"from": "generate_report", "to": "audit_log", "condition": "true", "priority": 100},
        ],
        "metadata": {"owner": "secops", "tags": ["scan", "runtime"]},
    }


def _publish_scan_workflow(client, admin_token) -> str:
    workflow_key = f"scan-runtime-{uuid4().hex[:8]}"
    payload = {
        "workflow_key": workflow_key,
        "name": f"Scan Runtime {workflow_key}",
        "description": "scan runtime workflow",
        "dsl": _scan_workflow_dsl(workflow_key),
        "change_note": "initial draft",
    }
    headers = _auth(admin_token)
    create_resp = client.post("/api/v1/workflows", json=payload, headers=headers)
    assert create_resp.status_code == 200
    workflow_id = create_resp.json()["data"]["id"]
    publish_resp = client.post(
        f"/api/v1/workflows/{workflow_id}/publish",
        json={
            "version_tag": 1,
            "canary_percent": 100,
            "approval_reason": "publish scan runtime",
            "approval_passed": True,
            "confirmation_text": workflow_key,
        },
        headers=headers,
    )
    assert publish_resp.status_code == 200
    return workflow_key


def test_scan_runtime_workflow_runs_to_report(monkeypatch, client, admin_token, test_db):
    workflow_key = _publish_scan_workflow(client, admin_token)
    asset = Asset(
        target="192.168.56.10",
        target_type="IP",
        tags="runtime,scan",
        priority=1,
        enabled=1,
        description="scan runtime asset",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    test_db.add(asset)
    test_db.commit()
    test_db.refresh(asset)

    async def fake_run_scan_workflow(task_id: int, target: str, tool_name: str, profile, script_set, operator, timeout_seconds=None):
        task = test_db.query(ScanTask).filter(ScanTask.id == task_id).first()
        assert task is not None
        now = datetime.now(timezone.utc)
        task.state = "REPORTED"
        task.started_at = now
        task.ended_at = now
        task.raw_output_path = "/tmp/fake_scan.xml"
        finding = ScanFinding(
            scan_task_id=task_id,
            asset=target,
            port=443,
            service="https",
            vuln_id=None,
            cve="CVE-2026-0001",
            severity="HIGH",
            evidence="TLS service exposed",
            status="NEW",
            trace_id=task.trace_id,
            created_at=now,
            updated_at=now,
        )
        test_db.add(finding)
        test_db.commit()
        return {
            "task_id": task_id,
            "target": target,
            "status": "success",
            "output_file": "/tmp/fake_scan.xml",
            "findings": [{"port": 443, "service": "https", "severity": "HIGH"}],
        }

    async def fake_generate_report(report_type: str, data: dict, trace_id=None, with_meta=False):
        result = {
            "text": "# Scan Runtime Report\n发现 1 条高危漏洞。",
            "degraded": False,
            "fallback_reason": None,
            "provider": "test",
            "model": "fake",
            "trace_id": trace_id,
        }
        return result if with_meta else result["text"]

    monkeypatch.setattr(workflow_runtime_module.scanner, "_run_scan_workflow", fake_run_scan_workflow)
    monkeypatch.setattr(workflow_runtime_module.ai_engine, "generate_report", fake_generate_report)

    result = workflow_runtime_module.asyncio.run(
        run_published_workflow(
            test_db,
            workflow_key=workflow_key,
            input_payload={"asset_id": asset.id},
            trigger_source="scan_runtime_test",
            trigger_ref=f"scan-runtime-{asset.id}",
            actor="tester",
        )
    )

    assert result.run_state == "SUCCESS"

    scan_task = test_db.query(ScanTask).order_by(ScanTask.id.desc()).first()
    assert scan_task is not None
    assert scan_task.state == "REPORTED"
    assert scan_task.target == asset.target

    finding = test_db.query(ScanFinding).filter(ScanFinding.scan_task_id == scan_task.id).first()
    assert finding is not None
    assert finding.severity == "HIGH"

    report = test_db.query(AIReport).order_by(AIReport.id.desc()).first()
    assert report is not None
    assert report.report_type == "scan"
    assert report.detail_path

    workflow_run = (
        test_db.query(WorkflowRun)
        .filter(WorkflowRun.trigger_ref == f"scan-runtime-{asset.id}")
        .order_by(WorkflowRun.id.desc())
        .first()
    )
    assert workflow_run is not None
    assert workflow_run.run_state == "SUCCESS"

    steps = (
        test_db.query(WorkflowStepRun)
        .filter(WorkflowStepRun.workflow_run_id == workflow_run.id)
        .order_by(WorkflowStepRun.id.asc())
        .all()
    )
    assert [step.node_id for step in steps] == [
        "trigger_scan",
        "select_asset",
        "create_task",
        "parse_result",
        "generate_report",
        "audit_log",
    ]
    assert all(step.step_state == "SUCCESS" for step in steps)
