from __future__ import annotations

import ast
import asyncio
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Mapping, Optional

from sqlalchemy.orm import Session

from core.database import WorkflowDefinition, WorkflowRun, WorkflowStepRun, WorkflowVersion
from services.ai_engine import ai_engine
from services.audit_service import AuditService
from services.mcp_client import mcp_client
from services.workflow_dsl import WorkflowDSL, WorkflowNode, WorkflowRunState, validate_workflow_dsl

WorkflowAdapter = Callable[["WorkflowAdapterInput"], Awaitable["NodeExecutionResult"]]


@dataclass(slots=True)
class CompiledTransition:
    to_node: str
    condition: str
    priority: int


@dataclass(slots=True)
class CompiledNode:
    id: str
    node_type: str
    name: str
    timeout: int
    config: dict[str, Any]
    retry_policy: Any
    transitions: list[CompiledTransition] = field(default_factory=list)


@dataclass(slots=True)
class CompiledWorkflow:
    workflow_key: str
    version: int
    start_node_id: str
    terminal_node_ids: set[str]
    nodes: dict[str, CompiledNode]
    runtime_states: set[str]
    terminal_states: set[str]


@dataclass(slots=True)
class WorkflowAdapterInput:
    db: Session
    actor: str
    trace_id: str
    workflow_run: WorkflowRun
    node: CompiledNode
    input_payload: dict[str, Any]
    context: dict[str, Any]


@dataclass(slots=True)
class WorkflowRuntimeResult:
    run_id: int
    workflow_id: int
    workflow_version_id: int
    run_state: str
    trace_id: str
    reused_existing: bool = False
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NodeExecutionResult:
    state: str
    output: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


_ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.Compare,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    data = json.loads(value)
    return data if isinstance(data, dict) else {}


def _normalize_condition(condition: str) -> str:
    expr = condition.strip() or "false"
    expr = re.sub(r"\btrue\b", "True", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bfalse\b", "False", expr, flags=re.IGNORECASE)
    expr = expr.replace("&&", " and ").replace("||", " or ")
    return expr


def _validate_condition_ast(condition: str) -> ast.Expression:
    tree = ast.parse(_normalize_condition(condition), mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_AST_NODES):
            raise ValueError(f"unsupported condition syntax: {condition}")
    return tree


class WorkflowRuntimeError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, output: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.retryable = retryable
        self.output = output or {}


def _evaluate_condition(condition: str, variables: Mapping[str, Any]) -> bool:
    tree = _validate_condition_ast(condition)
    try:
        value = eval(compile(tree, "<workflow-condition>", "eval"), {"__builtins__": {}}, dict(variables))
    except NameError:
        return False
    return bool(value)


def load_published_workflow(db: Session, workflow_key: str) -> tuple[WorkflowDefinition, WorkflowVersion, WorkflowDSL]:
    definition = (
        db.query(WorkflowDefinition)
        .filter(WorkflowDefinition.workflow_key == workflow_key)
        .first()
    )
    if definition is None or definition.published_version is None:
        raise ValueError(f"published workflow not found: {workflow_key}")

    version = (
        db.query(WorkflowVersion)
        .filter(
            WorkflowVersion.workflow_id == definition.id,
            WorkflowVersion.version == definition.published_version,
        )
        .first()
    )
    if version is None:
        raise ValueError(f"published workflow version not found: {workflow_key}@{definition.published_version}")
    return definition, version, validate_workflow_dsl(_json_loads(version.dsl_json))


def compile_workflow(payload: dict[str, Any] | WorkflowDSL) -> CompiledWorkflow:
    dsl = payload if isinstance(payload, WorkflowDSL) else validate_workflow_dsl(payload)

    nodes: dict[str, CompiledNode] = {
        node.id: CompiledNode(
            id=node.id,
            node_type=node.type,
            name=node.name,
            timeout=node.timeout,
            config=dict(node.config),
            retry_policy=node.retry_policy,
        )
        for node in dsl.nodes
    }
    incoming_count = {node_id: 0 for node_id in nodes}

    for edge in dsl.edges:
        _validate_condition_ast(edge.condition)
        incoming_count[edge.to_node] += 1
        nodes[edge.from_node].transitions.append(
            CompiledTransition(
                to_node=edge.to_node,
                condition=edge.condition,
                priority=edge.priority,
            )
        )

    start_nodes = sorted(node_id for node_id, count in incoming_count.items() if count == 0)
    if len(start_nodes) != 1:
        raise ValueError(f"workflow requires exactly one entry node, got {len(start_nodes)}")

    for node in nodes.values():
        node.transitions.sort(key=lambda item: (item.priority, item.to_node))

    terminal_node_ids = {node_id for node_id, node in nodes.items() if not node.transitions}
    runtime_states = {state.value if isinstance(state, WorkflowRunState) else str(state) for state in dsl.runtime.state_enum}
    terminal_states = {state.value if isinstance(state, WorkflowRunState) else str(state) for state in dsl.runtime.terminal_states}

    if dsl.runtime.initial_state.value not in runtime_states:
        raise ValueError("runtime.initial_state must exist in runtime.state_enum")
    if not terminal_states.issubset(runtime_states):
        raise ValueError("runtime.terminal_states must be a subset of runtime.state_enum")

    return CompiledWorkflow(
        workflow_key=dsl.workflow_id,
        version=dsl.version,
        start_node_id=start_nodes[0],
        terminal_node_ids=terminal_node_ids,
        nodes=nodes,
        runtime_states=runtime_states,
        terminal_states=terminal_states,
    )


def _extract_context_value(context: Mapping[str, Any], key: str, default: Any = None) -> Any:
    if key in context:
        return context[key]
    nested_input = context.get("input")
    if isinstance(nested_input, Mapping) and key in nested_input:
        return nested_input[key]
    event = context.get("event")
    if isinstance(event, Mapping) and key in event:
        return event[key]
    return default


def _merge_context(context: dict[str, Any], node_id: str, output: Mapping[str, Any]) -> None:
    steps = context.setdefault("steps", {})
    if isinstance(steps, dict):
        steps[node_id] = dict(output)
    context[node_id] = dict(output)
    for key, value in output.items():
        context[key] = value


def _build_initial_context(
    *,
    input_payload: Mapping[str, Any],
    trace_id: str,
    workflow_key: str,
    workflow_version: int,
    trigger_source: str,
    trigger_ref: str | None,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "input": dict(input_payload),
        "trace_id": trace_id,
        "workflow_key": workflow_key,
        "workflow_version": workflow_version,
        "trigger_source": trigger_source,
        "trigger_ref": trigger_ref,
        "steps": {},
    }
    context.update(dict(input_payload))
    event = input_payload.get("event")
    if isinstance(event, Mapping):
        context.setdefault("event", dict(event))
        for key, value in event.items():
            context.setdefault(str(key), value)
    return context


async def _trigger_adapter(payload: WorkflowAdapterInput) -> NodeExecutionResult:
    return NodeExecutionResult(
        state=WorkflowRunState.SUCCESS.value,
        output={
            "trigger_source": payload.context.get("trigger_source"),
            "trigger_ref": payload.context.get("trigger_ref"),
        },
    )


async def _manual_approval_adapter(payload: WorkflowAdapterInput) -> NodeExecutionResult:
    decisions = payload.context.get("approval_decisions")
    decision: Any = None
    if isinstance(decisions, Mapping):
        decision = decisions.get(payload.node.id)
    if decision is None:
        return NodeExecutionResult(
            state=WorkflowRunState.MANUAL_REQUIRED.value,
            output={"approved": None, "approval_required": True},
        )

    approved = bool(decision)
    approval_reason = None
    if isinstance(decision, Mapping):
        approved = bool(decision.get("approved"))
        raw_reason = decision.get("reason")
        approval_reason = str(raw_reason) if raw_reason is not None else None
    return NodeExecutionResult(
        state=WorkflowRunState.SUCCESS.value,
        output={"approved": approved, "approval_reason": approval_reason},
    )


async def _ai_assess_adapter(payload: WorkflowAdapterInput) -> NodeExecutionResult:
    ip = str(_extract_context_value(payload.context, "ip", "") or "")
    attack_type = str(_extract_context_value(payload.context, "threat_label", "") or "")
    attack_count = int(_extract_context_value(payload.context, "attack_count", 1) or 1)
    if not ip or not attack_type:
        raise WorkflowRuntimeError("ai_assess requires ip and threat_label")
    result = await ai_engine.assess_threat(
        ip=ip,
        attack_type=attack_type,
        attack_count=attack_count,
        history=str(_extract_context_value(payload.context, "history", "") or "") or None,
        trace_id=payload.trace_id,
    )
    return NodeExecutionResult(state=WorkflowRunState.SUCCESS.value, output=result)


async def _mcp_action_adapter(payload: WorkflowAdapterInput) -> NodeExecutionResult:
    service = str(payload.node.config.get("service") or "").strip()
    ip = str(_extract_context_value(payload.context, "ip", "") or "")
    device_id_raw = _extract_context_value(payload.context, "device_id", payload.node.config.get("device_id"))
    device_id = int(device_id_raw) if isinstance(device_id_raw, int) or (isinstance(device_id_raw, str) and device_id_raw.isdigit()) else None
    if not ip:
        raise WorkflowRuntimeError("mcp_action requires ip")

    if service == "mcp_client.block_ip":
        result = await mcp_client.block_ip(ip, device_id=device_id, operator=payload.actor)
    elif service == "mcp_client.unblock_ip":
        result = await mcp_client.unblock_ip(ip, device_id=device_id, operator=payload.actor)
    else:
        raise WorkflowRuntimeError(f"unsupported mcp action service: {service}")

    if not result.get("success"):
        raise WorkflowRuntimeError(
            str(result.get("error") or "mcp action failed"),
            retryable=bool(result.get("retryable")),
            output=result,
        )
    return NodeExecutionResult(
        state=WorkflowRunState.SUCCESS.value,
        output={"action_result": result, "action_service": service},
    )


async def _audit_adapter(payload: WorkflowAdapterInput) -> NodeExecutionResult:
    action = str(payload.node.config.get("action") or f"workflow_step:{payload.node.id}")
    target = str(payload.node.config.get("target") or f"workflow_run:{payload.workflow_run.id}")
    reason = payload.node.config.get("reason")
    if reason is None:
        reason = _json_dumps(
            {
                "workflow_key": payload.context.get("workflow_key"),
                "node_id": payload.node.id,
                "approved": payload.context.get("approved"),
                "score": payload.context.get("score"),
            }
        )
    AuditService.log(
        db=payload.db,
        actor=payload.actor,
        action=action,
        target=target,
        target_type="workflow_run",
        reason=str(reason),
        result="success",
        trace_id=payload.trace_id,
        auto_commit=False,
    )
    return NodeExecutionResult(state=WorkflowRunState.SUCCESS.value, output={"audited": True})


_NODE_TYPE_ADAPTERS: dict[str, WorkflowAdapter] = {
    "trigger": _trigger_adapter,
    "manual_approval": _manual_approval_adapter,
    "approval": _manual_approval_adapter,
    "ai_assess": _ai_assess_adapter,
    "mcp_action": _mcp_action_adapter,
    "audit": _audit_adapter,
}

_SERVICE_ADAPTERS: dict[str, WorkflowAdapter] = {
    "ai_engine.assess_threat": _ai_assess_adapter,
    "mcp_client.block_ip": _mcp_action_adapter,
    "mcp_client.unblock_ip": _mcp_action_adapter,
    "audit_service.log": _audit_adapter,
    "AuditService.log": _audit_adapter,
}


def _resolve_adapter(node: CompiledNode, adapters: Optional[Mapping[str, WorkflowAdapter]] = None) -> WorkflowAdapter:
    service = str(node.config.get("service") or "").strip()
    if adapters and service and service in adapters:
        return adapters[service]
    if adapters and node.node_type in adapters:
        return adapters[node.node_type]
    if service and service in _SERVICE_ADAPTERS:
        return _SERVICE_ADAPTERS[service]
    if node.node_type in _NODE_TYPE_ADAPTERS:
        return _NODE_TYPE_ADAPTERS[node.node_type]
    raise WorkflowRuntimeError(f"no adapter registered for node {node.id}")


def _update_run(
    db: Session,
    workflow_run: WorkflowRun,
    *,
    state: str,
    context: Mapping[str, Any],
    ended: bool = False,
) -> None:
    now = _utc_now()
    workflow_run.run_state = state
    workflow_run.context_json = _json_dumps(context)
    workflow_run.updated_at = now
    if workflow_run.started_at is None and state != WorkflowRunState.QUEUED.value:
        workflow_run.started_at = now
    if ended:
        workflow_run.ended_at = now
    db.commit()


def _create_step_run(
    db: Session,
    *,
    workflow_run: WorkflowRun,
    workflow_id: int,
    workflow_version_id: int,
    node: CompiledNode,
    attempt: int,
    trace_id: str,
    input_payload: Mapping[str, Any],
) -> WorkflowStepRun:
    step = WorkflowStepRun(
        workflow_run_id=workflow_run.id,
        workflow_id=workflow_id,
        workflow_version_id=workflow_version_id,
        node_id=node.id,
        node_type=node.node_type,
        step_state=WorkflowRunState.QUEUED.value,
        attempt=attempt,
        input_payload=_json_dumps(input_payload),
        trace_id=trace_id,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


async def _execute_node(
    db: Session,
    *,
    workflow_run: WorkflowRun,
    workflow_id: int,
    workflow_version_id: int,
    node: CompiledNode,
    actor: str,
    trace_id: str,
    context: dict[str, Any],
    adapters: Optional[Mapping[str, WorkflowAdapter]] = None,
) -> NodeExecutionResult:
    max_attempts = int(getattr(node.retry_policy, "max_retries", 0)) + 1
    backoff_seconds = int(getattr(node.retry_policy, "backoff_seconds", 1))
    backoff_multiplier = float(getattr(node.retry_policy, "backoff_multiplier", 1.0))
    adapter = _resolve_adapter(node, adapters)

    for attempt in range(1, max_attempts + 1):
        step = _create_step_run(
            db,
            workflow_run=workflow_run,
            workflow_id=workflow_id,
            workflow_version_id=workflow_version_id,
            node=node,
            attempt=attempt,
            trace_id=trace_id,
            input_payload=context,
        )
        step.step_state = WorkflowRunState.RUNNING.value
        step.started_at = _utc_now()
        step.updated_at = _utc_now()
        db.commit()

        try:
            result = await asyncio.wait_for(
                adapter(
                    WorkflowAdapterInput(
                        db=db,
                        actor=actor,
                        trace_id=trace_id,
                        workflow_run=workflow_run,
                        node=node,
                        input_payload=dict(context),
                        context=context,
                    )
                ),
                timeout=node.timeout,
            )
            if result.state == WorkflowRunState.MANUAL_REQUIRED.value:
                step.step_state = WorkflowRunState.MANUAL_REQUIRED.value
                step.output_payload = _json_dumps(result.output)
                step.ended_at = _utc_now()
                step.updated_at = _utc_now()
                db.commit()
                return result

            step.step_state = WorkflowRunState.SUCCESS.value
            step.output_payload = _json_dumps(result.output)
            step.error_message = None
            step.ended_at = _utc_now()
            step.updated_at = _utc_now()
            db.commit()
            return result
        except asyncio.TimeoutError as exc:
            error = WorkflowRuntimeError(f"node timeout: {node.id}", retryable=True)
        except WorkflowRuntimeError as exc:
            error = exc
        except Exception as exc:
            error = WorkflowRuntimeError(str(exc), retryable=False)

        should_retry = error.retryable and attempt < max_attempts
        step.step_state = WorkflowRunState.RETRYING.value if should_retry else WorkflowRunState.FAILED.value
        step.error_message = str(error)
        step.output_payload = _json_dumps(error.output)
        step.ended_at = _utc_now()
        step.updated_at = _utc_now()
        db.commit()

        if not should_retry:
            raise error

        _update_run(db, workflow_run, state=WorkflowRunState.RETRYING.value, context=context)
        delay = backoff_seconds * (backoff_multiplier ** (attempt - 1))
        await asyncio.sleep(delay)
        _update_run(db, workflow_run, state=WorkflowRunState.RUNNING.value, context=context)

    raise WorkflowRuntimeError(f"node execution exhausted: {node.id}")


def _select_next_node(node: CompiledNode, context: Mapping[str, Any]) -> str | None:
    if not node.transitions:
        return None
    for transition in node.transitions:
        if _evaluate_condition(transition.condition, context):
            return transition.to_node
    raise WorkflowRuntimeError(f"no transition matched for node {node.id}")


def _find_existing_run(
    db: Session,
    *,
    workflow_id: int,
    trigger_source: str,
    trigger_ref: str | None,
) -> WorkflowRun | None:
    if not trigger_ref:
        return None
    return (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.workflow_id == workflow_id,
            WorkflowRun.trigger_source == trigger_source,
            WorkflowRun.trigger_ref == trigger_ref,
        )
        .order_by(WorkflowRun.id.desc())
        .first()
    )


async def run_compiled_workflow(
    db: Session,
    *,
    definition: WorkflowDefinition,
    version: WorkflowVersion,
    compiled: CompiledWorkflow,
    input_payload: Mapping[str, Any],
    trigger_source: str,
    trigger_ref: str | None = None,
    actor: str = "system",
    trace_id: str | None = None,
    adapters: Optional[Mapping[str, WorkflowAdapter]] = None,
) -> WorkflowRuntimeResult:
    final_trace_id = trace_id or str(input_payload.get("trace_id") or uuid.uuid4())
    existing = _find_existing_run(
        db,
        workflow_id=definition.id,
        trigger_source=trigger_source,
        trigger_ref=trigger_ref,
    )
    if existing is not None:
        return WorkflowRuntimeResult(
            run_id=existing.id,
            workflow_id=existing.workflow_id,
            workflow_version_id=existing.workflow_version_id,
            run_state=existing.run_state,
            trace_id=existing.trace_id,
            reused_existing=True,
            context=_json_loads(existing.context_json),
        )

    context = _build_initial_context(
        input_payload=input_payload,
        trace_id=final_trace_id,
        workflow_key=compiled.workflow_key,
        workflow_version=compiled.version,
        trigger_source=trigger_source,
        trigger_ref=trigger_ref,
    )
    workflow_run = WorkflowRun(
        workflow_id=definition.id,
        workflow_version_id=version.id,
        run_state=WorkflowRunState.QUEUED.value,
        trigger_source=trigger_source,
        trigger_ref=trigger_ref,
        input_payload=_json_dumps(input_payload),
        context_json=_json_dumps(context),
        trace_id=final_trace_id,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    db.add(workflow_run)
    db.commit()
    db.refresh(workflow_run)

    current_node_id = compiled.start_node_id
    _update_run(db, workflow_run, state=WorkflowRunState.RUNNING.value, context=context)
    try:
        while current_node_id is not None:
            node = compiled.nodes[current_node_id]
            result = await _execute_node(
                db,
                workflow_run=workflow_run,
                workflow_id=definition.id,
                workflow_version_id=version.id,
                node=node,
                actor=actor,
                trace_id=final_trace_id,
                context=context,
                adapters=adapters,
            )
            _merge_context(context, node.id, result.output)
            if result.state == WorkflowRunState.MANUAL_REQUIRED.value:
                _update_run(db, workflow_run, state=WorkflowRunState.MANUAL_REQUIRED.value, context=context, ended=True)
                return WorkflowRuntimeResult(
                    run_id=workflow_run.id,
                    workflow_id=definition.id,
                    workflow_version_id=version.id,
                    run_state=workflow_run.run_state,
                    trace_id=final_trace_id,
                    context=dict(context),
                )

            next_node_id = _select_next_node(node, context)
            if next_node_id is None:
                _update_run(db, workflow_run, state=WorkflowRunState.SUCCESS.value, context=context, ended=True)
                return WorkflowRuntimeResult(
                    run_id=workflow_run.id,
                    workflow_id=definition.id,
                    workflow_version_id=version.id,
                    run_state=workflow_run.run_state,
                    trace_id=final_trace_id,
                    context=dict(context),
                )
            current_node_id = next_node_id
    except WorkflowRuntimeError as exc:
        context["last_error"] = str(exc)
        _update_run(db, workflow_run, state=WorkflowRunState.FAILED.value, context=context, ended=True)
        return WorkflowRuntimeResult(
            run_id=workflow_run.id,
            workflow_id=definition.id,
            workflow_version_id=version.id,
            run_state=workflow_run.run_state,
            trace_id=final_trace_id,
            context=dict(context),
        )


async def run_published_workflow(
    db: Session,
    *,
    workflow_key: str,
    input_payload: Mapping[str, Any],
    trigger_source: str,
    trigger_ref: str | None = None,
    actor: str = "system",
    trace_id: str | None = None,
    adapters: Optional[Mapping[str, WorkflowAdapter]] = None,
) -> WorkflowRuntimeResult:
    definition, version, dsl = load_published_workflow(db, workflow_key)
    compiled = compile_workflow(dsl)
    return await run_compiled_workflow(
        db,
        definition=definition,
        version=version,
        compiled=compiled,
        input_payload=input_payload,
        trigger_source=trigger_source,
        trigger_ref=trigger_ref,
        actor=actor,
        trace_id=trace_id,
        adapters=adapters,
    )
