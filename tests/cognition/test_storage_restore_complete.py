"""Atomic snapshot storage and complete cognitive-state restoration tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from ix_sally.cognition import (
    ActionSpec,
    CognitiveValue,
    FactEffect,
    FactPattern,
    SallyCognitiveSystem,
)
from ix_sally.cognition.curriculum import (
    Curriculum,
    CurriculumLedger,
    CurriculumSplit,
    CurriculumTask,
    CurriculumTrial,
    TrialStatus,
)
from ix_sally.cognition.episodes import (
    CognitiveEpisode,
    EpisodeStep,
    EpisodeStepKind,
    EpisodeStepStatus,
)
from ix_sally.cognition.goals import GoalSpec
from ix_sally.cognition.storage import SnapshotRepository, SnapshotSource
from ix_sally.cognition.uncertainty import CalibrationObservation
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError


def _digest(name: str) -> DigestRecord:
    return DigestRecord.from_payload({"evidence": name})


def _pattern(value: str) -> FactPattern:
    return FactPattern.create(
        subject="system",
        predicate="state",
        value=CognitiveValue.from_python(value),
    )


def _populated_system() -> SallyCognitiveSystem:
    system = SallyCognitiveSystem.create()
    system.execute_ix("remember answer = 40 + 2\n", filename="snapshot.ix")
    system.register_action(
        ActionSpec.create(
            action_id="ready-system",
            description="Move the simulated system to ready state.",
            preconditions=(),
            effects=(
                FactEffect.create(
                    subject="system",
                    predicate="state",
                    value=CognitiveValue.from_python("ready"),
                ),
            ),
            cost=1.0,
            risk=0.1,
        )
    )
    system.register_goal(
        GoalSpec.create(
            goal_id="ready-system",
            description="Reach ready state.",
            desired_state=_pattern("ready"),
            priority=1.0,
            utility=1.0,
            risk_limit=0.2,
        )
    )
    system.record_calibration(
        CalibrationObservation.create(
            observation_id="planning-calibration",
            capability_id="planning",
            predicted_probability=0.8,
            observed=True,
            evidence_digest=_digest("planning-calibration"),
            context="Observed deterministic planning result.",
        )
    )
    task = CurriculumTask.create(
        task_id="basic-planning",
        family="planning",
        description="Complete a basic planning task.",
        difficulty=1,
        split=CurriculumSplit.TRAINING,
        required_capabilities=("planning",),
    )
    system.set_curriculum(CurriculumLedger(Curriculum.create((task,))))
    system.record_curriculum_trial(
        CurriculumTrial.create(
            trial_id="basic-planning-trial",
            task_id="basic-planning",
            sequence=0,
            score=0.9,
            status=TrialStatus.PASSED,
            evidence_digest=_digest("basic-planning-trial"),
            notes="Observed successful trial.",
        )
    )
    before = system.digest()
    step = EpisodeStep.create(
        index=0,
        kind=EpisodeStepKind.PLANNING,
        status=EpisodeStepStatus.COMPLETED,
        detail="Produced a bounded plan.",
        input_digests=(before,),
        output_digests=(_digest("plan"),),
    )
    episode = CognitiveEpisode.create(
        episode_id="episode-zero",
        sequence=0,
        task="Plan ready state.",
        initial_state_digest=before,
        final_state_digest=system.digest(),
        steps=(step,),
    )
    system.append_episode(episode)
    return system


def test_complete_snapshot_restores_every_extended_subsystem() -> None:
    """Snapshot restoration must reproduce the full canonical state exactly."""
    system = _populated_system()
    snapshot = system.snapshot()

    restored = SallyCognitiveSystem.from_snapshot(snapshot)

    assert restored.state_payload() == system.state_payload()
    assert restored.digest() == system.digest()
    assert restored.runtime_memories["answer"] == CognitiveValue.from_python(42)
    assert restored.goals.require("ready-system").description == "Reach ready state."
    assert restored.curriculum is not None
    assert len(restored.episodes.episodes) == 1


def test_snapshot_repository_writes_and_loads_primary(tmp_path: Path) -> None:
    """A persisted snapshot must verify before the save receipt succeeds."""
    system = _populated_system()
    repository = SnapshotRepository(tmp_path / "state.json")

    receipt = repository.save(system.snapshot())
    loaded = repository.load()

    assert receipt.bytes_written > 0
    assert loaded.source is SnapshotSource.PRIMARY
    assert loaded.snapshot.state_digest == system.digest()


def test_snapshot_repository_recovers_last_valid_backup(tmp_path: Path) -> None:
    """A corrupted primary must not hide the separately validated backup."""
    repository = SnapshotRepository(tmp_path / "state.json")
    first = _populated_system()
    repository.save(first.snapshot())
    second = _populated_system()
    second.execute_ix("remember second = 2\n", filename="second.ix")
    second_snapshot = second.snapshot()
    receipt = repository.save(second_snapshot)
    assert receipt.backup_created
    repository.path.write_text("{broken", encoding="utf-8")

    loaded = repository.load()

    assert loaded.source is SnapshotSource.BACKUP
    assert loaded.snapshot.state_digest == first.snapshot().state_digest
    assert loaded.primary_error is not None


def test_snapshot_repository_fails_when_primary_and_backup_are_invalid(
    tmp_path: Path,
) -> None:
    """Recovery must fail closed when no valid state remains."""
    repository = SnapshotRepository(tmp_path / "state.json")
    repository.path.write_text("bad", encoding="utf-8")
    repository.backup_path.write_text("also bad", encoding="utf-8")

    with pytest.raises(FoundationError, match="primary and backup"):
        repository.load()
