"""Episode replay-chain and curriculum progression tests."""

from __future__ import annotations

import pytest
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
    EpisodeLedger,
    EpisodeStep,
    EpisodeStepKind,
    EpisodeStepStatus,
)
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError


def _digest(value: str) -> DigestRecord:
    return DigestRecord.from_payload({"value": value})


def _episode(
    sequence: int,
    previous: DigestRecord | None,
    *,
    status: EpisodeStepStatus = EpisodeStepStatus.COMPLETED,
) -> CognitiveEpisode:
    step = EpisodeStep.create(
        index=0,
        kind=EpisodeStepKind.PLANNING,
        status=status,
        detail="Bounded planning step.",
        input_digests=(_digest(f"input-{sequence}"),),
        output_digests=(_digest(f"output-{sequence}"),),
    )
    return CognitiveEpisode.create(
        episode_id=f"episode-{sequence}",
        sequence=sequence,
        task="Evaluate a bounded task.",
        initial_state_digest=_digest(f"before-{sequence}"),
        final_state_digest=_digest(f"after-{sequence}"),
        steps=(step,),
        previous_episode_digest=previous,
    )


def test_episode_ledger_requires_exact_chain_links() -> None:
    """Each episode must bind to the digest of the prior episode."""
    first = _episode(0, None)
    second = _episode(1, first.digest())

    ledger = EpisodeLedger.create((first, second))

    assert ledger.head_digest() == second.digest()
    assert ledger.next_sequence() == 2


def test_episode_ledger_rejects_wrong_previous_digest() -> None:
    """A valid-looking episode must fail when its history link is wrong."""
    first = _episode(0, None)
    second = _episode(1, _digest("wrong"))

    with pytest.raises(FoundationError, match="previous digest"):
        EpisodeLedger.create((first, second))


def test_episode_steps_require_contiguous_indexes() -> None:
    """Replay order must not contain unrecorded gaps."""
    with pytest.raises(FoundationError, match="contiguous"):
        CognitiveEpisode.create(
            episode_id="broken",
            sequence=0,
            task="Broken episode.",
            initial_state_digest=_digest("before"),
            final_state_digest=_digest("after"),
            steps=(
                EpisodeStep.create(
                    index=1,
                    kind=EpisodeStepKind.INPUT,
                    status=EpisodeStepStatus.COMPLETED,
                    detail="Out of order.",
                ),
            ),
        )


def test_failed_episode_is_not_reported_complete() -> None:
    """A failed step must remain visible at episode level."""
    episode = _episode(0, None, status=EpisodeStepStatus.FAILED)

    assert not episode.completed()


def _task(
    task_id: str,
    split: CurriculumSplit,
    *,
    prerequisites: tuple[str, ...] = (),
    difficulty: int = 1,
) -> CurriculumTask:
    return CurriculumTask.create(
        task_id=task_id,
        family="symbolic-reasoning",
        description=f"Complete {task_id}.",
        difficulty=difficulty,
        split=split,
        prerequisite_ids=prerequisites,
        required_capabilities=("planning", "reasoning"),
        pass_threshold=0.8,
    )


def _trial(
    trial_id: str,
    task_id: str,
    sequence: int,
    score: float,
) -> CurriculumTrial:
    return CurriculumTrial.create(
        trial_id=trial_id,
        task_id=task_id,
        sequence=sequence,
        score=score,
        status=TrialStatus.PASSED if score >= 0.8 else TrialStatus.PARTIAL,
        evidence_digest=_digest(trial_id),
        notes="Observed deterministic curriculum result.",
    )


def test_curriculum_eligibility_follows_prerequisites() -> None:
    """Advanced tasks become eligible only after prerequisite evidence passes."""
    basic = _task("basic", CurriculumSplit.TRAINING)
    advanced = _task(
        "advanced",
        CurriculumSplit.VALIDATION,
        prerequisites=("basic",),
        difficulty=2,
    )
    ledger = CurriculumLedger(Curriculum.create((basic, advanced)))

    assert tuple(task.task_id.value for task in ledger.eligible_tasks()) == ("basic",)

    updated = ledger.record(_trial("basic-pass", "basic", 0, 0.9))

    assert tuple(task.task_id.value for task in updated.eligible_tasks()) == (
        "advanced",
    )


def test_curriculum_reports_held_out_transfer_gap() -> None:
    """Held-out performance must remain separate from validation performance."""
    tasks = Curriculum.create(
        (
            _task("training", CurriculumSplit.TRAINING),
            _task("validation", CurriculumSplit.VALIDATION),
            _task("held-out", CurriculumSplit.HELD_OUT),
        )
    )
    ledger = CurriculumLedger(tasks)
    ledger = ledger.record(_trial("t1", "training", 0, 1.0))
    ledger = ledger.record(_trial("t2", "validation", 1, 0.9))
    ledger = ledger.record(_trial("t3", "held-out", 2, 0.7))

    assert ledger.split_score(CurriculumSplit.TRAINING) == 1.0
    assert ledger.split_score(CurriculumSplit.VALIDATION) == 0.9
    assert ledger.split_score(CurriculumSplit.HELD_OUT) == 0.7
    assert ledger.transfer_gap() == 0.2


def test_curriculum_rejects_unknown_prerequisite() -> None:
    """Curriculum construction must fail on a missing dependency."""
    with pytest.raises(FoundationError, match="unknown prerequisites"):
        Curriculum.create(
            (
                _task(
                    "advanced",
                    CurriculumSplit.HELD_OUT,
                    prerequisites=("missing",),
                ),
            )
        )


def test_curriculum_trial_sequence_is_append_only() -> None:
    """Trial history must not accept skipped sequence numbers."""
    curriculum = Curriculum.create((_task("task", CurriculumSplit.TRAINING),))
    with pytest.raises(FoundationError, match="sequence must be contiguous"):
        CurriculumLedger(
            curriculum,
            (_trial("late", "task", 1, 0.9),),
        )
