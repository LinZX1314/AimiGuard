from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from pydantic import ValidationError

from services.workflow_dsl import WorkflowDSL, validate_workflow_dsl

PUBLISH_TIMEOUT_LIMIT_SECONDS = 600
PUBLISH_MAX_RETRIES = 3

NODE_TYPE_CATEGORY = {
    "trigger": "trigger",
    "condition": "condition",
    "approval": "approval",
    "manual_approval": "approval",
    "action": "action",
    "mcp_action": "action",
    "notification": "notification",
    "ai": "ai",
    "ai_assess": "ai",
    "audit": "audit",
}

SERVICE_ADAPTERS = {
    "action": {"mcp_client.block_ip", "mcp_client.unblock_ip"},
    "notification": {
        "push_service.send_test",
        "PushService.send_test",
        "tts_service.synthesize",
        "TTSService.synthesize",
    },
    "ai": {"ai_engine.assess_threat", "ai_engine.analyze_scan_result"},
    "audit": {"audit_service.log", "AuditService.log"},
}

DANGEROUS_CONFIG_KEYS = {
    "command",
    "cmd",
    "shell",
    "script",
    "powershell",
    "bash",
    "exec",
    "subprocess",
    "raw_sql",
}

DANGEROUS_VALUE_PATTERNS = [
    re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
    re.compile(r"\bcurl\b.+\|\s*(bash|sh)", re.IGNORECASE),
    re.compile(r"\bwget\b.+\|\s*(bash|sh)", re.IGNORECASE),
    re.compile(r"\bbash\s+-c\b", re.IGNORECASE),
    re.compile(r"\bpowershell\b", re.IGNORECASE),
    re.compile(r"\binvoke-expression\b", re.IGNORECASE),
    re.compile(r"\bsubprocess\b", re.IGNORECASE),
    re.compile(r"\beval\s*\(", re.IGNORECASE),
    re.compile(r"\bexec\s*\(", re.IGNORECASE),
]


def _path(loc: tuple[Any, ...]) -> str:
    parts: list[str] = []
    for item in loc:
        if isinstance(item, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{item}]"
            else:
                parts.append(f"[{item}]")
            continue
        parts.append(str(item))
    return ".".join(parts) if parts else "dsl"


def _issue(code: str, category: str, message: str, path: str, **extra: Any) -> dict[str, Any]:
    issue = {
        "code": code,
        "category": category,
        "level": "error",
        "message": message,
        "path": path,
    }
    for key, value in extra.items():
        if value is not None:
            issue[key] = value
    return issue


def _dedupe(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for issue in issues:
        fingerprint = "|".join(
            [
                str(issue.get("code") or ""),
                str(issue.get("path") or ""),
                str(issue.get("message") or ""),
                str(issue.get("node_id") or ""),
                str(issue.get("value") or ""),
            ]
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        result.append(issue)
    return result


def _schema_errors(exc: ValidationError) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for item in exc.errors():
        message = str(item.get("msg") or "workflow schema validation failed")
        lowered = message.lower()
        path = _path(tuple(item.get("loc") or ()))
        if "duplicate node id found in workflow nodes" in lowered:
            issues.append(_issue("WF_STRUCT_DUPLICATE_NODE", "structure", "存在重复的节点 ID。", "nodes"))
            continue
        if "edge.from references unknown node" in lowered or "edge.to references unknown node" in lowered:
            issues.append(_issue("WF_STRUCT_ORPHAN_EDGE", "structure", message.replace("Value error, ", ""), path))
            continue
        issues.append(_issue("WF_SCHEMA_INVALID", "structure", message, path))
    return _dedupe(issues) or [_issue("WF_SCHEMA_INVALID", "structure", "workflow schema validation failed", "dsl")]


def _build_graph(dsl: WorkflowDSL) -> tuple[set[str], dict[str, list[str]], dict[str, int], dict[str, list[Any]]]:
    node_ids = [node.id for node in dsl.nodes]
    adjacency = {node_id: [] for node_id in node_ids}
    indegree = {node_id: 0 for node_id in node_ids}
    outgoing: dict[str, list[Any]] = defaultdict(list)
    for edge in dsl.edges:
        adjacency[edge.from_node].append(edge.to_node)
        indegree[edge.to_node] += 1
        outgoing[edge.from_node].append(edge)
    return set(node_ids), adjacency, indegree, outgoing


def _find_cycle(adjacency: dict[str, list[str]]) -> list[str] | None:
    state = {node_id: 0 for node_id in adjacency}
    stack: list[str] = []

    def dfs(node_id: str) -> list[str] | None:
        state[node_id] = 1
        stack.append(node_id)
        for next_node in adjacency.get(node_id, []):
            if state[next_node] == 0:
                cycle = dfs(next_node)
                if cycle:
                    return cycle
            elif state[next_node] == 1:
                start = stack.index(next_node)
                return stack[start:] + [next_node]
        stack.pop()
        state[node_id] = 2
        return None

    for node_id in adjacency:
        if state[node_id] != 0:
            continue
        cycle = dfs(node_id)
        if cycle:
            return cycle
    return None


def _reachable(entry_nodes: list[str], adjacency: dict[str, list[str]]) -> set[str]:
    visited = set(entry_nodes)
    stack = list(entry_nodes)
    while stack:
        node_id = stack.pop()
        for next_node in adjacency.get(node_id, []):
            if next_node in visited:
                continue
            visited.add(next_node)
            stack.append(next_node)
    return visited


def _normalize_condition(value: str) -> str:
    normalized = " ".join((value or "true").strip().lower().split())
    return normalized or "true"


def _scan_config(value: Any, path: str, node_id: str, issues: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            child_path = f"{path}.{key}"
            if key.strip().lower() in DANGEROUS_CONFIG_KEYS:
                issues.append(_issue("WF_SEC_DANGEROUS_PARAM", "security", f"节点 {node_id} 使用了危险参数键 `{key}`。", child_path, node_id=node_id, value=key))
            _scan_config(raw_value, child_path, node_id, issues)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _scan_config(item, f"{path}[{index}]", node_id, issues)
        return
    if isinstance(value, str):
        snippet = value.strip()
        if snippet and any(pattern.search(snippet) for pattern in DANGEROUS_VALUE_PATTERNS):
            issues.append(_issue("WF_SEC_DANGEROUS_PARAM", "security", f"节点 {node_id} 存在危险参数值。", path, node_id=node_id, value=snippet[:120]))


def validate_workflow_publish(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        dsl = validate_workflow_dsl(payload)
    except ValidationError as exc:
        errors = _schema_errors(exc)
        return {
            "valid": False,
            "errors": errors,
            "warnings": [],
            "summary": {
                "error_count": len(errors),
                "warning_count": 0,
                "categories": {"structure": len(errors)},
            },
            "normalized_dsl": None,
        }

    errors: list[dict[str, Any]] = []
    node_set, adjacency, indegree, outgoing = _build_graph(dsl)

    cycle = _find_cycle(adjacency)
    if cycle:
        errors.append(_issue("WF_STRUCT_CYCLE", "structure", f"工作流存在循环依赖: {' -> '.join(cycle)}。", "edges"))

    trigger_nodes = [node.id for node in dsl.nodes if NODE_TYPE_CATEGORY.get(node.type) == "trigger"]
    entry_nodes = trigger_nodes or sorted(node_id for node_id, value in indegree.items() if value == 0)
    if entry_nodes:
        reached = _reachable(entry_nodes, adjacency)
        for node_id in sorted(node_set - reached):
            errors.append(_issue("WF_RULE_UNREACHABLE_NODE", "rule", f"节点 {node_id} 不可达。", "nodes", node_id=node_id))

    terminal_nodes = [node_id for node_id in sorted(node_set) if not adjacency[node_id]]
    if not terminal_nodes:
        errors.append(_issue("WF_RULE_NO_TERMINAL", "rule", "工作流缺少终止节点。", "runtime.terminal_states"))

    for source, edges in outgoing.items():
        if len(edges) <= 1:
            continue
        by_condition: dict[str, list[Any]] = defaultdict(list)
        by_priority: dict[int, list[Any]] = defaultdict(list)
        for edge in edges:
            by_condition[_normalize_condition(edge.condition)].append(edge)
            by_priority[int(edge.priority)].append(edge)
        if "true" in by_condition and len(edges) > 1:
            errors.append(_issue("WF_RULE_CONDITION_CONFLICT", "rule", f"节点 {source} 存在无条件分支冲突。", "edges", node_id=source))
        for condition, items in by_condition.items():
            if len(items) > 1:
                errors.append(_issue("WF_RULE_CONDITION_CONFLICT", "rule", f"节点 {source} 存在重复条件 `{condition}`。", "edges", node_id=source, value=condition))
        for priority, items in by_priority.items():
            if len(items) > 1:
                errors.append(_issue("WF_RULE_CONDITION_CONFLICT", "rule", f"节点 {source} 存在重复优先级 {priority}。", "edges", node_id=source, value=priority))

    for node in dsl.nodes:
        _scan_config(node.config, f"nodes[{node.id}].config", node.id, errors)
        if int(node.timeout) > PUBLISH_TIMEOUT_LIMIT_SECONDS:
            errors.append(_issue("WF_SEC_TIMEOUT_LIMIT", "security", f"节点 {node.id} 超时 {node.timeout}s 超出发布上限 {PUBLISH_TIMEOUT_LIMIT_SECONDS}s。", f"nodes[{node.id}].timeout", node_id=node.id, value=node.timeout))
        if int(node.retry_policy.max_retries) > PUBLISH_MAX_RETRIES:
            errors.append(_issue("WF_SEC_RETRY_LIMIT", "security", f"节点 {node.id} 重试次数 {node.retry_policy.max_retries} 超出发布上限 {PUBLISH_MAX_RETRIES}。", f"nodes[{node.id}].retry_policy.max_retries", node_id=node.id, value=node.retry_policy.max_retries))
        category = NODE_TYPE_CATEGORY.get(node.type)
        if category is None:
            errors.append(_issue("WF_COMPAT_NODE_TYPE_UNSUPPORTED", "compatibility", f"节点 {node.id} 的类型 `{node.type}` 无法映射现有适配器。", f"nodes[{node.id}].type", node_id=node.id, value=node.type))
            continue
        allowed = SERVICE_ADAPTERS.get(category)
        if not allowed:
            continue
        service = ""
        if isinstance(node.config, dict):
            service = str(node.config.get("service") or "").strip()
        if not service:
            errors.append(_issue("WF_COMPAT_SERVICE_MISSING", "compatibility", f"节点 {node.id} 缺少 service 映射。", f"nodes[{node.id}].config.service", node_id=node.id, allowed_values=sorted(allowed)))
            continue
        if service not in allowed:
            errors.append(_issue("WF_COMPAT_SERVICE_UNSUPPORTED", "compatibility", f"节点 {node.id} 的 service `{service}` 无法映射现有适配器。", f"nodes[{node.id}].config.service", node_id=node.id, value=service, allowed_values=sorted(allowed)))

    errors = _dedupe(errors)
    categories: dict[str, int] = defaultdict(int)
    for item in errors:
        categories[str(item.get("category") or "unknown")] += 1
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": [],
        "summary": {
            "error_count": len(errors),
            "warning_count": 0,
            "categories": dict(categories),
        },
        "normalized_dsl": dsl.model_dump(by_alias=True),
    }
