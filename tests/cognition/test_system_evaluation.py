"""Integrated system, persistence, ninefold, and evaluation tests."""

from __future__ import annotations

import json

import pytest

from ix_sally.agents import AgentRole
from ix_sally.cognition import (
    CognitiveSnapshot,
    CognitiveValue,
    SallyCognitiveSystem,
    VMStatus,
    run_core_evaluation,
)
from ix_sally.foundation import FoundationError


def test_system_commits_vm_memory_only_after_clean_halt() -> None:
    """Failed IX runs must not overwrite the system's committed runtime memory."""
    system = SallyCognitiveSystem.create()
    first = system.execute_ix("remember answer = 42\n", filename="first.ix")
    failed = system.execute_ix(
        "remember answer = 7\nassert false\n",
        filename="failed.ix",
    )

    assert first.status is VMStatus.HALTED
    assert failed.status is VMStatus.FAILED
    assert system.runtime_memories == {"answer": CognitiveValue.from_python(42)}


def test_system_state_digest_changes_after_state_transition() -> None:
    """Complete state identity must change when committed cognitive state changes."""
    system = SallyCognitiveSystem.create()
    before = system.digest()
    system.execute_ix("remember answer = 42\n", filename="state.ix")

    assert system.digest() != before


def test_snapshot_round_trip_preserves_exact_payload() -> None:
    """Canonical snapshot encoding must preserve all serialized state data."""
    system = SallyCognitiveSystem.create()
    system.execute_ix("remember answer = 42\n", filename="snapshot.ix")
    snapshot = system.snapshot()

    restored = CognitiveSnapshot.from_json(snapshot.to_json())

    assert restored == snapshot
    assert restored.state == system.state_payload()


def test_snapshot_rejects_tampered_state() -> None:
    """Changing state bytes without updating the digest must be detected."""
    snapshot = SallyCognitiveSystem.create().snapshot()
    payload = json.loads(snapshot.to_json())
    payload["state"]["execution_count"] = 999

    with pytest.raises(FoundationError, match="digest mismatch"):
        CognitiveSnapshot.from_json(json.dumps(payload))


def test_ninefold_cycle_covers_each_role_once() -> None:
    """Functional coordination must cover the complete canonical ninefold."""
    cycle = SallyCognitiveSystem.create().run_cycle(task="Inspect current state")

    assert len(cycle.findings) == 9
    assert {finding.role for finding in cycle.findings} == set(AgentRole)
    assert cycle.digest().algorithm == "sha256"


def test_core_evaluation_runs_real_benchmarks_without_agi_certification() -> None:
    """The built-in suite must pass its observed checks but never self-certify AGI."""
    report = run_core_evaluation()

    assert len(report.results) == 15
    assert report.passed() == 15
    assert report.overall_score() == 1.0
    assert report.agi_certified is False
    assert report.classification == "experimental-cognitive-architecture"


def test_evaluation_is_repeatable() -> None:
    """Fresh deterministic evaluations must produce identical report identities."""
    first = run_core_evaluation()
    second = run_core_evaluation()

    assert first.to_payload() == second.to_payload()
    assert first.digest() == second.digest()
