

from __future__ import annotations

import pytest
from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_decision_ledger import (
    HumanReviewDecisionLedger,
    HumanReviewDecisionLedgerEntry,
)
from ix_sally.human_review_gateway import (
    HumanReviewDecisionStatus,
    HumanReviewGateway,
    HumanReviewTargetType,
)
from ix_sally.orchestration import StageOrchestrator
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Ledger human-review decisions.",
        mode=AutonomyMode.TEST,
        max_cycles=2,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _human_boundary_action() -> BoundedActionRecord:
    return BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.SALLY,
        description="Run a human-boundary verification step.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload(
            {"proposal_action": "human boundary action"},
        ),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=True,
    )


def _human_review_state() -> NinefoldRunState:
    result = StageOrchestrator.create().advance_once(
        state=_state().with_action(_human_boundary_action()),
    )
    assert result.state.human_review_action_count() == 1
    return result.state


def _submission(status: HumanReviewDecisionStatus = HumanReviewDecisionStatus.DEFERRED):
    state = _human_review_state()
    action = state.actions.human_review_actions()[0]

    return HumanReviewGateway.create().decide_action(
        state=state,
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=status,
        rationale="Operator decision for ledger coverage.",
    )


def test_human_review_decision_ledger_entry_records_deferred_submission() -> None:
    submission = _submission(HumanReviewDecisionStatus.DEFERRED)

    entry = HumanReviewDecisionLedgerEntry.from_submission(
        sequence=1,
        submission=submission,
    )

    assert entry.sequence == 1
    assert entry.status is HumanReviewDecisionStatus.DEFERRED
    assert entry.deferred_target() is True
    assert entry.changed_state is True
    assert entry.changed_action is False
    assert entry.next_stage is RunStage.HUMAN_REVIEW
    assert entry.target_id == submission.decision.target_id


def test_human_review_decision_ledger_entry_records_approved_submission() -> None:
    submission = _submission(HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION)

    entry = HumanReviewDecisionLedgerEntry.from_submission(
        sequence=1,
        submission=submission,
    )

    assert entry.approved_target() is True
    assert entry.changed_action is True
    assert entry.next_stage is RunStage.EXECUTION_PLANNING


def test_human_review_decision_ledger_appends_submission_at_next_sequence() -> None:
    submission = _submission(HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION)
    ledger = HumanReviewDecisionLedger.create(())

    updated = ledger.append_submission(submission)

    assert updated.next_sequence() == 2
    assert updated.latest() is not None
    assert updated.latest().decision_digest == submission.decision.digest()
    assert updated.approved_entries() == (updated.latest(),)


def test_human_review_decision_ledger_rejects_duplicate_decision_digest() -> None:
    submission = _submission(HumanReviewDecisionStatus.DEFERRED)
    first = HumanReviewDecisionLedgerEntry.from_submission(
        sequence=1,
        submission=submission,
    )
    duplicate = HumanReviewDecisionLedgerEntry.from_submission(
        sequence=2,
        submission=submission,
    )

    with pytest.raises(FoundationError, match="duplicate human-review decision digest"):
        HumanReviewDecisionLedger.create((first, duplicate))


def test_human_review_decision_ledger_rejects_duplicate_sequence() -> None:
    first = HumanReviewDecisionLedgerEntry.from_submission(
        sequence=1,
        submission=_submission(HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION),
    )
    second = HumanReviewDecisionLedgerEntry.from_submission(
        sequence=1,
        submission=_submission(HumanReviewDecisionStatus.REJECTED),
    )

    with pytest.raises(
        FoundationError,
        match="duplicate human-review decision ledger sequence",
    ):
        HumanReviewDecisionLedger.create((first, second))


def test_human_review_decision_ledger_filters_by_target() -> None:
    submission = _submission(HumanReviewDecisionStatus.REJECTED)
    ledger = HumanReviewDecisionLedger.create(()).append_submission(submission)

    entries = ledger.entries_for_target(
        target_type=HumanReviewTargetType.BOUNDED_ACTION,
        target_id=submission.decision.target_id.value,
    )

    assert entries == (ledger.latest(),)
    assert ledger.rejected_entries() == (ledger.latest(),)
    assert ledger.approved_entries() == ()
    assert ledger.deferred_entries() == ()


def test_human_review_decision_ledger_entry_rejects_empty_reviewer() -> None:
    submission = _submission(HumanReviewDecisionStatus.DEFERRED)

    with pytest.raises(FoundationError, match="reviewer must not be empty"):
        HumanReviewDecisionLedgerEntry.create(
            sequence=1,
            decision_digest=submission.decision.digest(),
            receipt_digest=submission.receipt.digest(),
            before_state_digest=submission.before_snapshot.state_digest,
            after_state_digest=submission.state.digest(),
            before_action_digest=submission.before_action.digest(),
            after_action_digest=submission.after_action.digest(),
            target_type=submission.decision.target_type,
            target_id=submission.decision.target_id.value,
            reviewer="   ",
            status=submission.decision.status,
            next_stage=submission.next_snapshot().stage,
            changed_state=submission.receipt.changed_state(),
            changed_action=submission.receipt.changed_action(),
        )


def test_human_review_decision_ledger_payload_and_digest_are_stable() -> None:
    submission = _submission(HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION)

    first = HumanReviewDecisionLedger.create(()).append_submission(submission)
    second = HumanReviewDecisionLedger.create(()).append_submission(submission)

    payload = first.to_payload()
    latest = first.latest()

    assert latest is not None
    assert payload["entry_count"] == 1
    assert payload["next_sequence"] == 2
    assert payload["latest_entry_digest"] == latest.digest().value
    assert payload["approved_count"] == 1
    assert payload["rejected_count"] == 0
    assert payload["deferred_count"] == 0
    assert first.digest() == second.digest()
