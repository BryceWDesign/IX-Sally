"""Grounded primitive and cognitive workspace tests."""

from __future__ import annotations

import pytest
from ix_sally.cognition import (
    CognitiveValue,
    CognitiveWorkspace,
    PrimitiveExecutor,
    PrimitiveKind,
    PrimitiveOperation,
    PrimitiveRegistry,
    PrimitiveSpec,
    PrimitiveStatus,
    WorkspaceItem,
    WorkspaceItemKind,
    WorkspaceItemStatus,
    default_primitive_registry,
)
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError


def test_default_primitive_registry_executes_validated_operations() -> None:
    """Built-in primitives must be real closed operations, not dynamic placeholders."""
    execution = PrimitiveExecutor(default_primitive_registry()).execute(
        "multiply-two",
        (CognitiveValue.from_python(6), CognitiveValue.from_python(7)),
    )

    assert execution.output == CognitiveValue.from_python(42)
    assert execution.digest().algorithm == "sha256"


def test_candidate_primitive_cannot_execute() -> None:
    """Unvalidated primitive candidates must fail closed."""
    candidate = PrimitiveSpec.create(
        primitive_id="candidate-identity",
        kind=PrimitiveKind.TRANSFORM,
        operation=PrimitiveOperation.IDENTITY,
        arity=1,
        status=PrimitiveStatus.CANDIDATE,
        description="Candidate identity operation.",
    )
    executor = PrimitiveExecutor(PrimitiveRegistry.create((candidate,)))

    with pytest.raises(FoundationError, match="not validated"):
        executor.execute("candidate-identity", (CognitiveValue.from_python(1),))


def test_validated_primitive_requires_grounding_and_validation_evidence() -> None:
    """Lifecycle state alone must not create executable authority."""
    with pytest.raises(FoundationError, match="grounding evidence"):
        PrimitiveSpec.create(
            primitive_id="invalid",
            kind=PrimitiveKind.TRANSFORM,
            operation=PrimitiveOperation.IDENTITY,
            arity=1,
            status=PrimitiveStatus.VALIDATED,
            description="Invalid evidence-free primitive.",
        )


def test_primitive_arity_is_enforced() -> None:
    """Primitive execution must reject missing operands."""
    with pytest.raises(FoundationError, match="requires 2 inputs"):
        PrimitiveExecutor(default_primitive_registry()).execute(
            "add-two",
            (CognitiveValue.from_python(1),),
        )


def test_workspace_focus_prioritizes_risk_and_goal_salience() -> None:
    """Attention selection must be deterministic and visible."""
    workspace = CognitiveWorkspace(capacity=3)
    belief = WorkspaceItem.create(
        item_id="belief",
        kind=WorkspaceItemKind.BELIEF,
        content="A low-priority belief.",
        confidence=0.9,
        salience=0.2,
    )
    goal = WorkspaceItem.create(
        item_id="goal",
        kind=WorkspaceItemKind.GOAL,
        content="A high-priority goal.",
        confidence=0.8,
        salience=0.9,
    )
    risk = WorkspaceItem.create(
        item_id="risk",
        kind=WorkspaceItemKind.RISK,
        content="A high-priority risk.",
        confidence=0.7,
        salience=1.0,
    )
    for item in (belief, goal, risk):
        workspace = workspace.admit(item)

    assert tuple(item.item_id.value for item in workspace.focus()) == (
        "risk",
        "goal",
        "belief",
    )


def test_workspace_evicts_lowest_attention_on_overflow() -> None:
    """Capacity overflow must evict deterministically rather than grow unbounded."""
    workspace = CognitiveWorkspace(capacity=2)
    for identifier, kind, salience in (
        ("low", WorkspaceItemKind.BELIEF, 0.1),
        ("goal", WorkspaceItemKind.GOAL, 0.8),
        ("risk", WorkspaceItemKind.RISK, 1.0),
    ):
        workspace = workspace.admit(
            WorkspaceItem.create(
                item_id=identifier,
                kind=kind,
                content=f"Workspace item {identifier}.",
                confidence=0.8,
                salience=salience,
            )
        )

    assert {item.item_id.value for item in workspace.items} == {"goal", "risk"}


def test_observation_requires_full_confidence() -> None:
    """Direct observations must not be stored as partly observed facts."""
    with pytest.raises(FoundationError, match="observation confidence"):
        WorkspaceItem.create(
            item_id="weak-observation",
            kind=WorkspaceItemKind.OBSERVATION,
            content="A weakly stated observation.",
            confidence=0.5,
            salience=0.5,
        )


def test_workspace_replacement_preserves_capacity_and_identity() -> None:
    """Updating one item must not disturb unrelated workspace entries."""
    original = WorkspaceItem.create(
        item_id="goal",
        kind=WorkspaceItemKind.GOAL,
        content="Original goal.",
        confidence=0.8,
        salience=0.8,
    )
    workspace = CognitiveWorkspace((original,), capacity=2)
    replaced = WorkspaceItem.create(
        item_id="goal",
        kind=WorkspaceItemKind.GOAL,
        content="Completed goal.",
        confidence=1.0,
        salience=0.2,
        status=WorkspaceItemStatus.SATISFIED,
        evidence_digests=(DigestRecord.from_payload({"result": "complete"}),),
    )

    updated = workspace.replace(replaced)

    assert updated.items == (replaced,)
    assert updated.capacity == 2
