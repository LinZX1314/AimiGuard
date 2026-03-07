import json

import pytest
from pydantic import ValidationError

from services.workflow_dsl import (
    WorkflowDefinitionState,
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
