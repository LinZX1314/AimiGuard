import asyncio
from copy import deepcopy
from uuid import uuid4

import pytest

from core.database import WorkflowRun, WorkflowStepRun
from services.workflow_dsl import WorkflowRunState, load_default_defense_workflow
from services.workflow_runtime import (
    NodeExecutionResult,
    WorkflowRuntimeError,
    compile_workflow,
    run_published_workflow,
)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_payload() -> dict:
    suffix = uuid4().hex[:8]
    workflow_key = f"wf-m3-01-{suffix}"
    dsl = deepcopy(load_default_defense_workflow())
    dsl["workflow_id"] = workflow_key
    dsl["name"] = f"Workflow {suffix}"
    dsl["version"] = 1
    dsl["status"] = "DRAFT"
    return {
        "workflow_key": workflow_key,
        "name": dsl["name"],
        "description": "workflow runtime test",
        "dsl": dsl,
        "change_note": "initial draft",
    }


def _create_published_workflow(client, admin_token) -> tuple[int, str, dict]:
    headers = _auth(admin_token)
    payload = _create_payload()
    create_resp = client.post("/api/v1/workflows", json=payload, headers=headers)
    assert create_resp.status_code == 200
    workflow_id = create_resp.json()["data"]["id"]
    publish_resp = client.post(
        f"/api/v1/workflows/{workflow_id}/publish",
        json={
            "version_tag": 1,
            "canary_percent": 100,
            "approval_reason": "runtime test publish",
            "approval_passed": True,
            "confirmation_text": payload["workflow_key"],
        },
        headers=headers,
    )
    assert publish_resp.status_code == 200
    return workflow_id, payload["workflow_key"], payload


def test_compile_workflow_orders_transitions_and_requires_single_entry():
    payload = load_default_defense_workflow()
    compiled = compile_workflow(payload)

    assert compiled.start_node_id == "trigger_hfish"
    assert compiled.terminal_node_ids == {"audit_log"}
    assert [item.to_node for item in compiled.nodes["assess_ai"].transitions] == ["approval", "audit_log"]

    invalid = deepcopy(payload)
    invalid["nodes"].append(
        {
            "id": "dangling_node",
            "type": "audit",
            "name": "dangling",
            "config": {"service": "audit_service.log"},
            "timeout": 10,
            "retry_policy": {
                "max_retries": 0,
                "backoff_seconds": 1,
                "backoff_multiplier": 1.0,
                "retry_on": [],
            },
        }
    )
    with pytest.raises(ValueError, match="exactly one entry node"):
        compile_workflow(invalid)


def test_runtime_enters_manual_required_when_approval_missing(client, admin_token, test_db):
    _, workflow_key, _ = _create_published_workflow(client, admin_token)

    async def ai_high(_payload):
        return NodeExecutionResult(
            state=WorkflowRunState.SUCCESS.value,
            output={"score": 90, "reason": "high", "action_suggest": "BLOCK"},
        )

    result = asyncio.run(
        run_published_workflow(
            test_db,
            workflow_key=workflow_key,
            input_payload={
                "event": {"ip": "10.0.0.8", "attack_count": 3, "threat_label": "bruteforce"}
            },
            trigger_source="unit_test",
            trigger_ref="event-manual-required",
            actor="tester",
            adapters={"ai_engine.assess_threat": ai_high},
        )
    )

    assert result.run_state == WorkflowRunState.MANUAL_REQUIRED.value
    run_row = test_db.query(WorkflowRun).filter(WorkflowRun.id == result.run_id).first()
    assert run_row is not None
    assert run_row.run_state == WorkflowRunState.MANUAL_REQUIRED.value

    approval_step = (
        test_db.query(WorkflowStepRun)
        .filter(WorkflowStepRun.workflow_run_id == result.run_id, WorkflowStepRun.node_id == "approval")
        .first()
    )
    assert approval_step is not None
    assert approval_step.step_state == WorkflowRunState.MANUAL_REQUIRED.value


def test_runtime_retries_action_and_finishes_success(client, admin_token, test_db):
    _, workflow_key, _ = _create_published_workflow(client, admin_token)
    counters = {"mcp": 0, "audit": 0}

    async def ai_high(_payload):
        return NodeExecutionResult(
            state=WorkflowRunState.SUCCESS.value,
            output={"score": 92, "reason": "high", "action_suggest": "BLOCK"},
        )

    async def mcp_retry(_payload):
        counters["mcp"] += 1
        if counters["mcp"] == 1:
            raise WorkflowRuntimeError("temporary downstream error", retryable=True, output={"success": False})
        return NodeExecutionResult(
            state=WorkflowRunState.SUCCESS.value,
            output={"action_result": {"success": True}, "action_service": "mcp_client.block_ip"},
        )

    async def audit_ok(_payload):
        counters["audit"] += 1
        return NodeExecutionResult(state=WorkflowRunState.SUCCESS.value, output={"audited": True})

    result = asyncio.run(
        run_published_workflow(
            test_db,
            workflow_key=workflow_key,
            input_payload={
                "event": {"ip": "10.0.0.9", "attack_count": 4, "threat_label": "rce"},
                "approval_decisions": {"approval": {"approved": True, "reason": "approved"}},
            },
            trigger_source="unit_test",
            trigger_ref="event-retry-success",
            actor="tester",
            adapters={
                "ai_engine.assess_threat": ai_high,
                "mcp_client.block_ip": mcp_retry,
                "audit_service.log": audit_ok,
            },
        )
    )

    assert result.run_state == WorkflowRunState.SUCCESS.value
    assert counters["mcp"] == 2
    assert counters["audit"] == 1

    block_steps = (
        test_db.query(WorkflowStepRun)
        .filter(WorkflowStepRun.workflow_run_id == result.run_id, WorkflowStepRun.node_id == "block_action")
        .order_by(WorkflowStepRun.attempt.asc())
        .all()
    )
    assert [step.step_state for step in block_steps] == [WorkflowRunState.RETRYING.value, WorkflowRunState.SUCCESS.value]


def test_runtime_is_idempotent_by_trigger_ref(client, admin_token, test_db):
    _, workflow_key, _ = _create_published_workflow(client, admin_token)
    counters = {"ai": 0, "audit": 0}

    async def ai_low(_payload):
        counters["ai"] += 1
        return NodeExecutionResult(
            state=WorkflowRunState.SUCCESS.value,
            output={"score": 30, "reason": "low", "action_suggest": "MONITOR"},
        )

    async def audit_ok(_payload):
        counters["audit"] += 1
        return NodeExecutionResult(state=WorkflowRunState.SUCCESS.value, output={"audited": True})

    first = asyncio.run(
        run_published_workflow(
            test_db,
            workflow_key=workflow_key,
            input_payload={
                "event": {"ip": "10.0.0.10", "attack_count": 1, "threat_label": "scan"}
            },
            trigger_source="unit_test",
            trigger_ref="event-idempotent",
            actor="tester",
            adapters={"ai_engine.assess_threat": ai_low, "audit_service.log": audit_ok},
        )
    )
    second = asyncio.run(
        run_published_workflow(
            test_db,
            workflow_key=workflow_key,
            input_payload={
                "event": {"ip": "10.0.0.10", "attack_count": 1, "threat_label": "scan"}
            },
            trigger_source="unit_test",
            trigger_ref="event-idempotent",
            actor="tester",
            adapters={"ai_engine.assess_threat": ai_low, "audit_service.log": audit_ok},
        )
    )

    assert first.reused_existing is False
    assert second.reused_existing is True
    assert second.run_id == first.run_id
    assert counters == {"ai": 1, "audit": 1}

    run_rows = test_db.query(WorkflowRun).filter(WorkflowRun.trigger_ref == "event-idempotent").all()
    assert len(run_rows) == 1
