from __future__ import annotations

import pytest

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_decision_coordinator import (
    HumanReviewDecisionCoordinationReceipt,
    HumanReviewDecisionCoordinator,
)
from ix_sally.human_review_decision_ledger import HumanReviewDecisionLedger
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.orchestration import StageOrchestrator
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Coordinate human-review decisions.",
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


def test_decision_coordinator_approves_action_and_appends_ledger() -> None:
    state = _human_review_state()
    action = state.actions.human_review_actions()[0]
    ledger = HumanReviewDecisionLedger.create(())

    result = HumanReviewDecisionCoordinator.create().decide_action(
        state=state,
        ledger=ledger,
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
        rationale="Bounded action is approved for the allowed test runner.",
    )

    assert result.before_ledger == ledger
    assert result.after_ledger.next_sequence() == 2
    assert result.latest_entry() == result.ledger_entry
    assert result.approved_target() is True
    assert result.rejected_target() is False
    assert result.deferred_target() is False
    assert result.ledger_entry.next_stage is RunStage.EXECUTION_PLANNING
    assert result.receipt.changed_ledger() is True
    assert result.state.actions.require_action(action.action_id.value).allows_execution()


def test_decision_coordinator_rejects_action_and_records_blocking_outcome() -> None:
    state = _human_review_state()
    action = state.actions.human_review_actions()[0]

    result = HumanReviewDecisionCoordinator.create().decide_action(
        state=state,
        ledger=HumanReviewDecisionLedger.create(()),
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.REJECTED,
        rationale="Boundary reviewer rejected the action.",
    )

    assert result.rejected_target() is True
    assert result.ledger_entry.next_stage is RunStage.HUMAN_REVIEW
    assert result.ledger_entry.changed_action is True
    assert result.state.actions.require_action(action.action_id.value).blocks_progress()


def test_decision_coordinator_defers_action_and_records_review_open() -> None:
    state = _human_review_state()
    action = state.actions.human_review_actions()[0]

    result = HumanReviewDecisionCoordinator.create().decide_action(
        state=state,
        ledger=HumanReviewDecisionLedger.create(()),
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.DEFERRED,
        rationale="Boundary reviewer needs additional information.",
    )

    assert result.deferred_target() is True
    assert result.ledger_entry.next_stage is RunStage.HUMAN_REVIEW
    assert result.ledger_entry.changed_state is True
    assert result.ledger_entry.changed_action is False
    assert result.state.actions.require_action(action.action_id.value) == action


def test_decision_coordinator_rejects_duplicate_decision_on_same_ledger() -> None:
    state = _human_review_state()
    action = state.actions.human_review_actions()[0]
    coordinator = HumanReviewDecisionCoordinator.create()
    first = coordinator.decide_action(
        state=state,
        ledger=HumanReviewDecisionLedger.create(()),
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.DEFERRED,
        rationale="Boundary reviewer needs additional information.",
    )

    with pytest.raises(FoundationError, match="duplicate human-review decision digest"):
        coordinator.decide_action(
            state=state,
            ledger=first.after_ledger,
            action_id=action.action_id.value,
            reviewer="Bryce Lovell",
            status=HumanReviewDecisionStatus.DEFERRED,
            rationale="Boundary reviewer needs additional information.",
        )


def test_decision_coordinator_rejects_non_human_review_state() -> None:
    with pytest.raises(
        FoundationError,
        match="expected human_review but observed proposal_intake",
    ):
        HumanReviewDecisionCoordinator.create().decide_action(
            state=_state(),
            ledger=HumanReviewDecisionLedger.create(()),
            action_id="missing-action",
            reviewer="Bryce Lovell",
            status=HumanReviewDecisionStatus.DEFERRED,
            rationale="Not reachable.",
        )


def test_decision_coordination_receipt_rejects_invalid_reviewer() -> None:
    digest = DigestRecord.from_payload({"record": "decision-coordination"})

    with pytest.raises(FoundationError, match="reviewer must not be empty"):
        HumanReviewDecisionCoordinationReceipt.create(
            before_ledger_digest=digest,
            after_ledger_digest=digest,
            submission_digest=digest,
            ledger_entry_digest=digest,
            decision_digest=digest,
            before_state_digest=digest,
            after_state_digest=digest,
            target_id="review-action",
            reviewer=" ",
            status=HumanReviewDecisionStatus.DEFERRED,
            next_stage=RunStage.HUMAN_REVIEW,
            changed_state=True,
            changed_action=False,
        )


def test_decision_coordination_result_payload_and_digest_are_stable() -> None:
    state = _human_review_state()
    action = state.actions.human_review_actions()[0]
    ledger = HumanReviewDecisionLedger.create(())

    first = HumanReviewDecisionCoordinator.create().decide_action(
        state=state,
        ledger=ledger,
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
        rationale="Bounded action is approved for the allowed test runner.",
    )
    second = HumanReviewDecisionCoordinator.create().decide_action(
        state=state,
        ledger=ledger,
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
        rationale="Bounded action is approved for the allowed test runner.",
    )

    payload = first.to_payload()

    assert payload["status"] == HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION.value
    assert payload["next_stage"] == RunStage.EXECUTION_PLANNING.value
    assert payload["changed_ledger"] is True
    assert payload["approved_target"] is True
    assert first.digest() == second.digest()
    assert first.receipt.digest() == second.receipt.digest()
