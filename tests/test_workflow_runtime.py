"""WorkflowRuntime tests — pure-logic helpers, condition eval, context, compile."""
import pytest
from unittest.mock import MagicMock

from services.workflow_runtime import (
    _evaluate_condition,
    _normalize_condition,
    _validate_condition_ast,
    _extract_context_value,
    _merge_context,
    _build_initial_context,
    _build_runtime_context,
    _normalize_scan_target_type,
    _extract_report_summary,
    _payload_summary,
    _json_dumps,
    _json_loads,
    _debug_recommendations,
    _resolve_resume_step,
    compile_workflow,
    WorkflowRuntimeError,
    NodeExecutionResult,
)
from services.workflow_dsl import validate_workflow_dsl


# ── _normalize_condition ──

def test_normalize_condition_true():
    assert "True" in _normalize_condition("true")


def test_normalize_condition_false():
    assert "False" in _normalize_condition("false")


def test_normalize_condition_and_or():
    result = _normalize_condition("a && b || c")
    assert " and " in result
    assert " or " in result


def test_normalize_condition_empty():
    assert _normalize_condition("") == "False"


# ── _validate_condition_ast ──

def test_validate_condition_simple():
    tree = _validate_condition_ast("true")
    assert tree is not None


def test_validate_condition_comparison():
    tree = _validate_condition_ast("score > 80")
    assert tree is not None


def test_validate_condition_unsafe_rejects():
    with pytest.raises(ValueError, match="unsupported"):
        _validate_condition_ast("__import__('os').system('rm')")


# ── _evaluate_condition ──

def test_evaluate_true():
    assert _evaluate_condition("true", {}) is True


def test_evaluate_false():
    assert _evaluate_condition("false", {}) is False


def test_evaluate_comparison():
    assert _evaluate_condition("score > 80", {"score": 90}) is True
    assert _evaluate_condition("score > 80", {"score": 50}) is False


def test_evaluate_and():
    assert _evaluate_condition("a && b", {"a": True, "b": True}) is True
    assert _evaluate_condition("a && b", {"a": True, "b": False}) is False


def test_evaluate_missing_var_returns_false():
    assert _evaluate_condition("unknown_var > 0", {}) is False


# ── _extract_context_value ──

def test_extract_direct():
    assert _extract_context_value({"ip": "10.0.0.1"}, "ip") == "10.0.0.1"


def test_extract_from_input():
    ctx = {"input": {"ip": "10.0.0.2"}}
    assert _extract_context_value(ctx, "ip") == "10.0.0.2"


def test_extract_from_event():
    ctx = {"event": {"ip": "10.0.0.3"}}
    assert _extract_context_value(ctx, "ip") == "10.0.0.3"


def test_extract_default():
    assert _extract_context_value({}, "missing", "default") == "default"


def test_extract_priority_direct_over_nested():
    ctx = {"ip": "direct", "input": {"ip": "nested"}}
    assert _extract_context_value(ctx, "ip") == "direct"


# ── _merge_context ──

def test_merge_context():
    ctx = {"steps": {}}
    _merge_context(ctx, "node1", {"result": "ok", "score": 85})
    assert ctx["steps"]["node1"]["result"] == "ok"
    assert ctx["node1"]["score"] == 85
    assert ctx["score"] == 85


# ── _build_initial_context ──

def test_build_initial_context():
    ctx = _build_initial_context(
        input_payload={"ip": "10.0.0.1", "event": {"type": "alert"}},
        trace_id="tr1",
        workflow_key="wf1",
        workflow_version=1,
        trigger_source="api",
        trigger_ref="ref1",
    )
    assert ctx["ip"] == "10.0.0.1"
    assert ctx["trace_id"] == "tr1"
    assert ctx["event"]["type"] == "alert"
    assert ctx["type"] == "alert"
    assert ctx["steps"] == {}


# ── _build_runtime_context ──

def test_build_runtime_context_without_initial():
    ctx = _build_runtime_context(
        input_payload={"x": 1},
        trace_id="tr2",
        workflow_key="wf2",
        workflow_version=2,
        trigger_source="scheduler",
        trigger_ref=None,
    )
    assert ctx["x"] == 1
    assert ctx["trace_id"] == "tr2"


def test_build_runtime_context_with_initial():
    initial = {"old_key": "old_val", "input": {"existing": True}, "last_error": "err"}
    ctx = _build_runtime_context(
        input_payload={"new_key": "new_val"},
        trace_id="tr3",
        workflow_key="wf3",
        workflow_version=3,
        trigger_source="api",
        trigger_ref=None,
        initial_context=initial,
    )
    assert ctx["old_key"] == "old_val"
    assert ctx["new_key"] == "new_val"
    assert ctx["input"]["existing"] is True
    assert ctx["input"]["new_key"] == "new_val"
    assert "last_error" not in ctx


# ── _normalize_scan_target_type ──

def test_normalize_scan_target_type():
    assert _normalize_scan_target_type("ip") == "host"
    assert _normalize_scan_target_type("host") == "host"
    assert _normalize_scan_target_type("cidr") == "network"
    assert _normalize_scan_target_type("network") == "network"
    assert _normalize_scan_target_type("domain") == "domain"
    assert _normalize_scan_target_type("unknown") == "host"
    assert _normalize_scan_target_type(None) == "host"


# ── _extract_report_summary ──

def test_extract_report_summary():
    md = "# 扫描报告\n\n详细内容..."
    assert _extract_report_summary(md, "fallback") == "扫描报告"


def test_extract_report_summary_empty():
    assert _extract_report_summary("", "fallback") == "fallback"


def test_extract_report_summary_none():
    assert _extract_report_summary(None, "fb") == "fb"


# ── _payload_summary ──

def test_payload_summary_short():
    assert _payload_summary('{"a": 1}') == '{"a": 1}'


def test_payload_summary_long():
    long_val = '{"key": "' + "x" * 200 + '"}'
    result = _payload_summary(long_val, limit=50)
    assert len(result) == 50
    assert result.endswith("...")


def test_payload_summary_none():
    assert _payload_summary(None) is None


# ── _json_dumps / _json_loads ──

def test_json_dumps():
    assert '"中文"' in _json_dumps({"key": "中文"})


def test_json_loads_empty():
    assert _json_loads(None) == {}
    assert _json_loads("") == {}


def test_json_loads_dict():
    assert _json_loads('{"a": 1}') == {"a": 1}


def test_json_loads_non_dict():
    assert _json_loads('"string"') == {}


# ── _debug_recommendations ──

def test_recommendations_timeout():
    recs = _debug_recommendations(None, "Operation timeout exceeded")
    assert any("timeout" in r for r in recs)


def test_recommendations_requires_ip():
    recs = _debug_recommendations(None, "mcp_action requires ip")
    assert any("ip" in r for r in recs)


def test_recommendations_manual_approval():
    step = MagicMock()
    step.node_type = "manual_approval"
    recs = _debug_recommendations(step, "pending")
    assert any("approval" in r for r in recs)


def test_recommendations_scan():
    step = MagicMock()
    step.node_type = "scan_task_create"
    recs = _debug_recommendations(step, "failed")
    assert any("扫描" in r for r in recs)


def test_recommendations_default():
    recs = _debug_recommendations(None, None)
    assert len(recs) >= 1


# ── _resolve_resume_step ──

def test_resolve_resume_step_failed():
    step1 = MagicMock()
    step1.step_state = "SUCCESS"
    step2 = MagicMock()
    step2.step_state = "FAILED"
    result = _resolve_resume_step([step1, step2])
    assert result is step2


def test_resolve_resume_step_manual():
    step = MagicMock()
    step.step_state = "MANUAL_REQUIRED"
    assert _resolve_resume_step([step]) is step


def test_resolve_resume_step_none():
    step = MagicMock()
    step.step_state = "SUCCESS"
    assert _resolve_resume_step([step]) is None


# ── compile_workflow ──

def _valid_dsl():
    return {
        "workflow_id": "test_compile",
        "name": "compile_test",
        "version": 1,
        "nodes": [
            {"id": "t1", "type": "trigger", "name": "trigger", "config": {}, "timeout": 30},
            {"id": "a1", "type": "condition", "name": "check", "config": {}, "timeout": 60},
        ],
        "edges": [{"from": "t1", "to": "a1", "condition": "true"}],
    }


def test_compile_workflow():
    compiled = compile_workflow(_valid_dsl())
    assert compiled.workflow_key == "test_compile"
    assert compiled.start_node_id == "t1"
    assert "a1" in compiled.terminal_node_ids
    assert len(compiled.nodes) == 2


def test_compile_workflow_from_dsl_object():
    dsl = validate_workflow_dsl(_valid_dsl())
    compiled = compile_workflow(dsl)
    assert compiled.start_node_id == "t1"


def test_compile_workflow_multiple_entries_raises():
    payload = {
        "workflow_id": "multi_entry",
        "name": "bad",
        "version": 1,
        "nodes": [
            {"id": "a", "type": "trigger", "name": "a", "config": {}},
            {"id": "b", "type": "trigger", "name": "b", "config": {}},
        ],
        "edges": [],
    }
    with pytest.raises(ValueError, match="exactly one entry node"):
        compile_workflow(payload)


# ── WorkflowRuntimeError ──

def test_runtime_error_fields():
    err = WorkflowRuntimeError("test error", retryable=True, output={"key": "val"})
    assert str(err) == "test error"
    assert err.retryable is True
    assert err.output == {"key": "val"}


def test_runtime_error_defaults():
    err = WorkflowRuntimeError("simple")
    assert err.retryable is False
    assert err.output == {}


# ── NodeExecutionResult ──

def test_node_execution_result():
    result = NodeExecutionResult(state="SUCCESS", output={"x": 1}, error_message=None)
    assert result.state == "SUCCESS"
    assert result.output == {"x": 1}
