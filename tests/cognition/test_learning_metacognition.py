"""Learning, transfer, self-model, and improvement-boundary tests."""

from __future__ import annotations

import pytest
from ix_sally.cognition import (
    CapabilityMeasure,
    ImprovementProposal,
    ImprovementStatus,
    LearningLedger,
    LearningOutcome,
    OutcomeStatus,
    SelfModel,
    TransferEvaluation,
)
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError


def _outcome(identifier: str, score: float) -> LearningOutcome:
    return LearningOutcome.create(
        outcome_id=identifier,
        skill_id="planning",
        task_family="novel-state",
        status=OutcomeStatus.SUCCESS if score >= 0.8 else OutcomeStatus.PARTIAL,
        score=score,
        evidence_digest=DigestRecord.from_payload({"outcome": identifier, "score": score}),
        notes="Observed deterministic task result.",
    )


def test_learning_ledger_updates_profile_from_observed_outcomes() -> None:
    """Skill estimates must derive from actual recorded outcomes."""
    ledger = LearningLedger().record(_outcome("one", 0.5)).record(_outcome("two", 1.0))
    profile = ledger.require_profile("planning")

    assert profile.attempts == 2
    assert profile.successes == 1
    assert profile.mean_score == 0.75
    assert profile.last_outcome_digest == ledger.outcomes[-1].digest()


def test_learning_rejects_duplicate_outcome_identity() -> None:
    """An outcome must not be counted twice."""
    outcome = _outcome("duplicate", 1.0)
    ledger = LearningLedger().record(outcome)

    with pytest.raises(FoundationError, match="already exists"):
        ledger.record(outcome)


def test_retention_score_uses_declared_recent_window() -> None:
    """Retention must be transparent rather than an opaque self-rating."""
    ledger = LearningLedger()
    for index, score in enumerate((0.2, 0.4, 0.8, 1.0), start=1):
        ledger = ledger.record(_outcome(f"outcome-{index}", score))

    assert ledger.retention_score("planning", recent_window=2) == 0.9


def test_transfer_evaluation_exposes_generalization_gap() -> None:
    """Transfer must compare familiar and held-out performance explicitly."""
    transfer = TransferEvaluation.create(
        skill_id="planning",
        familiar_score=0.95,
        novel_score=0.8,
        retention_score=0.85,
        evidence_digests=(DigestRecord.from_payload({"suite": "transfer"}),),
    )

    assert transfer.generalization_gap() == 0.15
    assert transfer.passes()


def test_self_model_requires_evidence_and_limits() -> None:
    """Capability scores must have evidence and an explicit limitation."""
    with pytest.raises(FoundationError, match="requires evidence"):
        CapabilityMeasure.create(
            capability_id="planning",
            score=0.8,
            evidence_digests=(),
            limitation="Only evaluated on a bounded local suite.",
        )


def test_self_model_reports_weakest_measure() -> None:
    """Metacognition must expose weakest measured capability deterministically."""
    evidence = DigestRecord.from_payload({"suite": "capabilities"})
    model = SelfModel().update(
        CapabilityMeasure.create(
            capability_id="memory",
            score=0.9,
            evidence_digests=(evidence,),
            limitation="Local deterministic retrieval only.",
        )
    ).update(
        CapabilityMeasure.create(
            capability_id="planning",
            score=0.6,
            evidence_digests=(evidence,),
            limitation="Exact-state planning only.",
        )
    )

    weakest = model.weakest()
    assert weakest is not None
    assert weakest.capability_id.value == "planning"


def test_improvement_proposal_cannot_self_approve() -> None:
    """A proposed change must remain blocked until a human decision digest exists."""
    proposal = ImprovementProposal.create(
        proposal_id="improve-planning",
        target_capability="planning",
        description="Expand bounded planning evaluation coverage.",
        expected_benefit=0.2,
        regression_risk=0.1,
        evidence_digests=(DigestRecord.from_payload({"gap": "planning"}),),
    )

    assert proposal.status is ImprovementStatus.PROPOSED
    assert not proposal.may_enter_validation()
    with pytest.raises(FoundationError, match="human decision digest"):
        ImprovementProposal.create(
            proposal_id="fake-approved",
            target_capability="planning",
            description="Invalid self-approved proposal.",
            expected_benefit=0.2,
            regression_risk=0.1,
            evidence_digests=(DigestRecord.from_payload({"gap": "planning"}),),
            status=ImprovementStatus.HUMAN_APPROVED,
        )


def test_human_decision_enables_validation_but_not_automatic_application() -> None:
    """Human approval permits validation; it does not execute a code change."""
    proposal = ImprovementProposal.create(
        proposal_id="improve-memory",
        target_capability="memory",
        description="Evaluate a revised retrieval scoring policy.",
        expected_benefit=0.1,
        regression_risk=0.1,
        evidence_digests=(DigestRecord.from_payload({"gap": "memory"}),),
    )
    approved = proposal.with_human_decision(
        approved=True,
        decision_digest=DigestRecord.from_payload({"human": "approved"}),
    )

    assert approved.status is ImprovementStatus.HUMAN_APPROVED
    assert approved.may_enter_validation()
