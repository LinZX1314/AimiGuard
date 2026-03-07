from copy import deepcopy
from uuid import uuid4

from services.workflow_dsl import load_default_defense_workflow
from services.workflow_validator import validate_workflow_publish


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _workflow_create_payload() -> dict:
    suffix = uuid4().hex[:8]
    workflow_key = f"wf-m2-02-{suffix}"
    dsl = deepcopy(load_default_defense_workflow())
    dsl["workflow_id"] = workflow_key
    dsl["name"] = f"Workflow {suffix}"
    dsl["version"] = 1
    dsl["status"] = "DRAFT"
    return {
        "workflow_key": workflow_key,
        "name": dsl["name"],
        "description": "workflow validator test",
        "dsl": dsl,
        "change_note": "initial draft",
    }


def _codes(result: dict) -> set[str]:
    return {str(item["code"]) for item in result["errors"]}


def test_publish_validator_accepts_default_workflow():
    payload = load_default_defense_workflow()
    result = validate_workflow_publish(payload)

    assert result["valid"] is True
    assert result["errors"] == []
    assert result["summary"]["error_count"] == 0
    assert result["normalized_dsl"]["workflow_id"] == payload["workflow_id"]


def test_publish_validator_maps_schema_errors_to_structured_codes():
    duplicate = deepcopy(load_default_defense_workflow())
    duplicate["nodes"].append(dict(duplicate["nodes"][0]))
    duplicate_result = validate_workflow_publish(duplicate)
    assert duplicate_result["valid"] is False
    assert "WF_STRUCT_DUPLICATE_NODE" in _codes(duplicate_result)

    broken = deepcopy(load_default_defense_workflow())
    broken["edges"][0]["to"] = "not_exists_node"
    broken_result = validate_workflow_publish(broken)
    assert broken_result["valid"] is False
    assert "WF_STRUCT_ORPHAN_EDGE" in _codes(broken_result)


def test_publish_validator_collects_m2_02_error_matrix():
    payload = deepcopy(load_default_defense_workflow())
    payload["nodes"].append(
        {
            "id": "dangling_notify",
            "type": "notification",
            "name": "Dangling Notify",
            "config": {
                "service": "unknown.adapter",
                "command": "bash -c whoami",
            },
            "timeout": 999,
            "retry_policy": {
                "max_retries": 9,
                "backoff_seconds": 3,
                "backoff_multiplier": 2.0,
                "retry_on": ["TIMEOUT"],
            },
        }
    )
    payload["edges"].append(
        {"from": "audit_log", "to": "trigger_hfish", "condition": "true", "priority": 100}
    )
    payload["edges"].append(
        {"from": "dangling_notify", "to": "trigger_hfish", "condition": "true", "priority": 100}
    )
    payload["edges"].append(
        {"from": "assess_ai", "to": "approval", "condition": "score >= 60", "priority": 10}
    )

    result = validate_workflow_publish(payload)
    codes = _codes(result)

    assert result["valid"] is False
    assert {
        "WF_STRUCT_CYCLE",
        "WF_RULE_UNREACHABLE_NODE",
        "WF_RULE_NO_TERMINAL",
        "WF_RULE_CONDITION_CONFLICT",
        "WF_SEC_DANGEROUS_PARAM",
        "WF_SEC_TIMEOUT_LIMIT",
        "WF_SEC_RETRY_LIMIT",
        "WF_COMPAT_SERVICE_UNSUPPORTED",
    }.issubset(codes)
    assert result["summary"]["error_count"] >= 8
    assert result["summary"]["categories"]["structure"] >= 1
    assert result["summary"]["categories"]["rule"] >= 1
    assert result["summary"]["categories"]["security"] >= 1
    assert result["summary"]["categories"]["compatibility"] >= 1


def test_workflow_api_validate_returns_structured_errors_and_preserves_draft_state(client, admin_token):
    headers = _auth(admin_token)
    payload = _workflow_create_payload()
    payload["dsl"]["nodes"].append(
        {
            "id": "notify_missing_service",
            "type": "notification",
            "name": "Notify Missing Service",
            "config": {},
            "timeout": 20,
            "retry_policy": {
                "max_retries": 0,
                "backoff_seconds": 3,
                "backoff_multiplier": 2.0,
                "retry_on": [],
            },
        }
    )
    payload["dsl"]["edges"].append(
        {"from": "audit_log", "to": "notify_missing_service", "condition": "true", "priority": 50}
    )

    create_resp = client.post("/api/v1/workflows", json=payload, headers=headers)
    assert create_resp.status_code == 200
    workflow_id = create_resp.json()["data"]["id"]

    validate_resp = client.post(f"/api/v1/workflows/{workflow_id}/validate", headers=headers)
    assert validate_resp.status_code == 200
    validate_body = validate_resp.json()
    assert validate_body["code"] == 0
    assert validate_body["data"]["valid"] is False
    assert validate_body["message"] == "workflow validation failed"
    assert any(item["code"] == "WF_COMPAT_SERVICE_MISSING" for item in validate_body["data"]["errors"])
    assert validate_body["data"]["summary"]["categories"]["compatibility"] >= 1

    detail_resp = client.get(f"/api/v1/workflows/{workflow_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail_body = detail_resp.json()
    assert detail_body["data"]["workflow"]["definition_state"] == "DRAFT"
