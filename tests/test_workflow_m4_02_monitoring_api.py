import asyncio
from uuid import uuid4

from services.workflow_runtime import run_published_workflow


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _workflow_dsl(workflow_key: str, *, include_manual: bool) -> dict:
    nodes = [
        {
            "id": "trigger_node",
            "type": "trigger",
            "name": "Trigger",
            "config": {"source_type": "monitoring-test"},
            "timeout": 10,
            "retry_policy": {"max_retries": 0, "backoff_seconds": 1, "backoff_multiplier": 1.0, "retry_on": []},
        }
    ]
    edges = []
    if include_manual:
        nodes.append(
            {
                "id": "manual_gate",
                "type": "manual_approval",
                "name": "Manual Gate",
                "config": {},
                "timeout": 10,
                "retry_policy": {"max_retries": 0, "backoff_seconds": 1, "backoff_multiplier": 1.0, "retry_on": []},
            }
        )
        edges.append({"from": "trigger_node", "to": "manual_gate", "condition": "true", "priority": 100})
    else:
        nodes.append(
            {
                "id": "audit_log",
                "type": "audit",
                "name": "Audit",
                "config": {"service": "audit_service.log"},
                "timeout": 10,
                "retry_policy": {"max_retries": 0, "backoff_seconds": 1, "backoff_multiplier": 1.0, "retry_on": []},
            }
        )
        edges.append({"from": "trigger_node", "to": "audit_log", "condition": "true", "priority": 100})

    return {
        "schema_version": "1.0.0",
        "workflow_id": workflow_key,
        "version": 1,
        "name": f"Monitoring {workflow_key}",
        "description": "workflow monitoring api test",
        "status": "DRAFT",
        "context": {
            "inputs": {"sample": {"type": "string"}},
            "outputs": {},
            "trace_id": "{{ trace_id }}",
        },
        "runtime": {
            "initial_state": "QUEUED",
            "terminal_states": ["SUCCESS", "FAILED", "MANUAL_REQUIRED", "CANCELLED"],
            "state_enum": ["QUEUED", "RUNNING", "RETRYING", "SUCCESS", "FAILED", "MANUAL_REQUIRED", "CANCELLED"],
        },
        "nodes": nodes,
        "edges": edges,
        "metadata": {"owner": "secops"},
    }


def _publish_workflow(client, admin_token, *, include_manual: bool) -> str:
    workflow_key = f"monitoring-{uuid4().hex[:8]}"
    payload = {
        "workflow_key": workflow_key,
        "name": f"Monitoring {workflow_key}",
        "description": "workflow monitoring api test",
        "dsl": _workflow_dsl(workflow_key, include_manual=include_manual),
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
            "approval_reason": "publish monitoring workflow",
            "approval_passed": True,
            "confirmation_text": workflow_key,
        },
        headers=headers,
    )
    assert publish_resp.status_code == 200
    return workflow_key


def test_workflow_monitoring_api_lists_runs_and_steps(client, admin_token, test_db):
    success_key = _publish_workflow(client, admin_token, include_manual=False)
    manual_key = _publish_workflow(client, admin_token, include_manual=True)

    success_result = asyncio.run(
        run_published_workflow(
            test_db,
            workflow_key=success_key,
            input_payload={"sample": "success"},
            trigger_source="monitoring_api_test",
            trigger_ref=f"run-success-{uuid4().hex[:6]}",
            actor="tester",
        )
    )
    manual_result = asyncio.run(
        run_published_workflow(
            test_db,
            workflow_key=manual_key,
            input_payload={"sample": "manual"},
            trigger_source="monitoring_api_test",
            trigger_ref=f"run-manual-{uuid4().hex[:6]}",
            actor="tester",
        )
    )

    assert success_result.run_state == "SUCCESS"
    assert manual_result.run_state == "MANUAL_REQUIRED"

    headers = _auth(admin_token)
    list_resp = client.get("/api/v1/workflows/runs", headers=headers)
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["summary"]["total_runs"] >= 2
    assert data["summary"]["success_runs"] >= 1
    assert data["summary"]["manual_required_runs"] >= 1
    assert data["summary"]["failure_rate"] >= 0

    success_item = next((item for item in data["items"] if item["run_id"] == success_result.run_id), None)
    assert success_item is not None
    assert success_item["workflow_key"] == success_key
    assert success_item["run_state"] == "SUCCESS"
    assert success_item["duration_ms"] is not None
    assert success_item["audit_path"].endswith(success_item["trace_id"])
    assert success_item["step_count"] == 2

    filtered_resp = client.get(
        "/api/v1/workflows/runs",
        params={"run_state": "MANUAL_REQUIRED"},
        headers=headers,
    )
    assert filtered_resp.status_code == 200
    filtered_items = filtered_resp.json()["data"]["items"]
    assert any(item["run_id"] == manual_result.run_id for item in filtered_items)

    detail_resp = client.get(f"/api/v1/workflows/runs/{success_result.run_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["run"]["workflow_key"] == success_key
    assert detail["run"]["input_payload"]["sample"] == "success"
    assert detail["run"]["context"]["trigger_source"] == "monitoring_api_test"
    assert len(detail["steps"]) == 2
    assert [step["node_id"] for step in detail["steps"]] == ["trigger_node", "audit_log"]
    assert all(step["audit_path"].endswith(step["trace_id"]) for step in detail["steps"])
