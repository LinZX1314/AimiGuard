"""WorkflowDSL tests — schema validation, enums, edges, retry, context, runtime."""
import json

import pytest
from pydantic import ValidationError

from services.workflow_dsl import (
    WorkflowDefinitionState,
    WorkflowRunState,
    WorkflowDSL,
    WorkflowNode,
    WorkflowEdge,
    RetryPolicy,
    WorkflowContext,
    RuntimeStateModel,
    WORKFLOW_SCHEMA_VERSION,
    load_default_defense_workflow,
    validate_workflow_dsl,
)


def test_default_defense_workflow_is_valid():
    payload = load_default_defense_workflow()
    dsl = validate_workflow_dsl(payload)

    assert dsl.schema_version == "1.0.0"
    assert dsl.status == WorkflowDefinitionState.DRAFT
    assert len(dsl.nodes) >= 1
    assert all(edge.from_node for edge in dsl.edges)
    assert all(edge.to_node for edge in dsl.edges)


def test_duplicate_node_id_rejected():
    payload = load_default_defense_workflow()
    duplicate = json.loads(json.dumps(payload))
    duplicate["nodes"].append(dict(duplicate["nodes"][0]))

    with pytest.raises(ValidationError):
        validate_workflow_dsl(duplicate)


def test_edge_with_unknown_node_rejected():
    payload = load_default_defense_workflow()
    broken = json.loads(json.dumps(payload))
    broken["edges"][0]["to"] = "not_exists_node"

    with pytest.raises(ValidationError):
        validate_workflow_dsl(broken)


# ── Enums ──

def test_definition_states():
    assert WorkflowDefinitionState.DRAFT.value == "DRAFT"
    assert WorkflowDefinitionState.PUBLISHED.value == "PUBLISHED"
    assert WorkflowDefinitionState.ARCHIVED.value == "ARCHIVED"


def test_run_states():
    assert WorkflowRunState.QUEUED.value == "QUEUED"
    assert WorkflowRunState.SUCCESS.value == "SUCCESS"
    assert WorkflowRunState.FAILED.value == "FAILED"
    assert WorkflowRunState.MANUAL_REQUIRED.value == "MANUAL_REQUIRED"


# ── RetryPolicy ──

def test_retry_policy_defaults():
    rp = RetryPolicy()
    assert rp.max_retries == 0
    assert rp.backoff_seconds == 5
    assert rp.backoff_multiplier == 2.0
    assert "TIMEOUT" in rp.retry_on


def test_retry_policy_bounds():
    with pytest.raises(ValidationError):
        RetryPolicy(max_retries=-1)
    with pytest.raises(ValidationError):
        RetryPolicy(max_retries=11)
    with pytest.raises(ValidationError):
        RetryPolicy(backoff_seconds=0)


def test_retry_policy_forbids_extra():
    with pytest.raises(ValidationError):
        RetryPolicy(unknown_field=True)


# ── WorkflowNode ──

def test_node_minimal():
    node = WorkflowNode(id="n1", type="trigger", name="entry")
    assert node.timeout == 60
    assert node.config == {}


def test_node_empty_id_rejected():
    with pytest.raises(ValidationError):
        WorkflowNode(id="", type="trigger", name="entry")


def test_node_forbids_extra():
    with pytest.raises(ValidationError):
        WorkflowNode(id="n1", type="t", name="n", unknown=True)


# ── WorkflowEdge ──

def test_edge_alias():
    edge = WorkflowEdge(**{"from": "a", "to": "b"})
    assert edge.from_node == "a"
    assert edge.to_node == "b"
    assert edge.condition == "true"
    assert edge.priority == 100


def test_edge_condition_max_length():
    with pytest.raises(ValidationError):
        WorkflowEdge(**{"from": "a", "to": "b", "condition": "x" * 501})


# ── WorkflowContext ──

def test_context_defaults():
    ctx = WorkflowContext()
    assert ctx.inputs == {}
    assert ctx.outputs == {}
    assert ctx.trace_id is None


# ── RuntimeStateModel ──

def test_runtime_defaults():
    rt = RuntimeStateModel()
    assert rt.initial_state == WorkflowRunState.QUEUED
    assert WorkflowRunState.SUCCESS in rt.terminal_states
    assert len(rt.state_enum) == 7


# ── WorkflowDSL ──

def _minimal_dsl():
    return {
        "workflow_id": "test_wf",
        "name": "Test Workflow",
        "version": 1,
        "nodes": [{"id": "n1", "type": "trigger", "name": "start"}],
        "edges": [],
    }


def test_minimal_dsl_valid():
    dsl = validate_workflow_dsl(_minimal_dsl())
    assert dsl.workflow_id == "test_wf"
    assert dsl.schema_version == WORKFLOW_SCHEMA_VERSION


def test_dsl_missing_workflow_id():
    payload = _minimal_dsl()
    del payload["workflow_id"]
    with pytest.raises(ValidationError):
        validate_workflow_dsl(payload)


def test_dsl_missing_name():
    payload = _minimal_dsl()
    del payload["name"]
    with pytest.raises(ValidationError):
        validate_workflow_dsl(payload)


def test_dsl_missing_nodes():
    payload = _minimal_dsl()
    payload["nodes"] = []
    with pytest.raises(ValidationError):
        validate_workflow_dsl(payload)


def test_dsl_version_must_be_positive():
    payload = _minimal_dsl()
    payload["version"] = 0
    with pytest.raises(ValidationError):
        validate_workflow_dsl(payload)


def test_dsl_forbids_extra():
    payload = _minimal_dsl()
    payload["unknown_field"] = True
    with pytest.raises(ValidationError):
        validate_workflow_dsl(payload)


def test_dsl_edge_from_unknown_rejected():
    payload = _minimal_dsl()
    payload["edges"] = [{"from": "ghost", "to": "n1"}]
    with pytest.raises(ValidationError):
        validate_workflow_dsl(payload)
