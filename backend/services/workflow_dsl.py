"""Workflow DSL v1 models and validation helpers."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


WORKFLOW_SCHEMA_VERSION = "1.0.0"
WORKFLOW_DIR = Path(__file__).resolve().parents[1] / "workflow"
DSL_SCHEMA_PATH = WORKFLOW_DIR / "dsl.schema.json"
DEFENSE_DEFAULT_PATH = WORKFLOW_DIR / "defense_default_v1.json"


class WorkflowDefinitionState(str, Enum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class WorkflowRunState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    RETRYING = "RETRYING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    MANUAL_REQUIRED = "MANUAL_REQUIRED"
    CANCELLED = "CANCELLED"


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_retries: int = Field(default=0, ge=0, le=10)
    backoff_seconds: int = Field(default=5, ge=1, le=3600)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=5.0)
    retry_on: List[str] = Field(default_factory=lambda: ["TIMEOUT", "NETWORK_ERROR"])


class WorkflowNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    type: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    config: Dict[str, Any] = Field(default_factory=dict)
    timeout: int = Field(default=60, ge=1, le=3600)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)


class WorkflowEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_node: str = Field(alias="from", min_length=1, max_length=80)
    to_node: str = Field(alias="to", min_length=1, max_length=80)
    condition: str = Field(default="true", min_length=1, max_length=500)
    priority: int = Field(default=100, ge=0, le=9999)


class WorkflowContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    trace_id: Optional[str] = Field(default=None, max_length=128)


class RuntimeStateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    initial_state: WorkflowRunState = WorkflowRunState.QUEUED
    terminal_states: List[WorkflowRunState] = Field(
        default_factory=lambda: [
            WorkflowRunState.SUCCESS,
            WorkflowRunState.FAILED,
            WorkflowRunState.MANUAL_REQUIRED,
            WorkflowRunState.CANCELLED,
        ]
    )
    state_enum: List[WorkflowRunState] = Field(
        default_factory=lambda: [
            WorkflowRunState.QUEUED,
            WorkflowRunState.RUNNING,
            WorkflowRunState.RETRYING,
            WorkflowRunState.SUCCESS,
            WorkflowRunState.FAILED,
            WorkflowRunState.MANUAL_REQUIRED,
            WorkflowRunState.CANCELLED,
        ]
    )


class WorkflowDSL(BaseModel):
    """Workflow DSL v1 payload."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=WORKFLOW_SCHEMA_VERSION)
    workflow_id: str = Field(min_length=1, max_length=80)
    version: int = Field(default=1, ge=1)
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    status: WorkflowDefinitionState = Field(default=WorkflowDefinitionState.DRAFT)
    context: WorkflowContext = Field(default_factory=WorkflowContext)
    runtime: RuntimeStateModel = Field(default_factory=RuntimeStateModel)
    nodes: List[WorkflowNode] = Field(min_length=1)
    edges: List[WorkflowEdge] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_graph(self) -> "WorkflowDSL":
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("duplicate node id found in workflow nodes")

        node_set = set(node_ids)
        for edge in self.edges:
            if edge.from_node not in node_set:
                raise ValueError(f"edge.from references unknown node: {edge.from_node}")
            if edge.to_node not in node_set:
                raise ValueError(f"edge.to references unknown node: {edge.to_node}")
        return self


def load_workflow_schema() -> Dict[str, Any]:
    return json.loads(DSL_SCHEMA_PATH.read_text(encoding="utf-8"))


def load_default_defense_workflow() -> Dict[str, Any]:
    return json.loads(DEFENSE_DEFAULT_PATH.read_text(encoding="utf-8"))


def validate_workflow_dsl(payload: Dict[str, Any]) -> WorkflowDSL:
    return WorkflowDSL.model_validate(payload)


def validate_default_workflow() -> WorkflowDSL:
    return validate_workflow_dsl(load_default_defense_workflow())

