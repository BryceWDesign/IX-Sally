

from __future__ import annotations

import pytest
from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_gateway import (
    HumanReviewDecisionStatus,
    HumanReviewGateway,
    HumanReviewSubmissionReceipt,
)
from ix_sally.orchestration import StageOrchestrator
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage, RunStageSnapshot
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Resolve a human-boundary action.",
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
    state = _state().with_action(_human_boundary_action())
    result = StageOrchestrator.create().advance_once(state=state)

    assert RunStageSnapshot.from_state(result.state).stage is RunStage.HUMAN_REVIEW
    assert result.state.human_review_action_count() == 1

    return result.state


def test_human_review_gateway_approves_action_for_execution_planning() -> None:
    state = _human_review_state()
    action = state.actions.human_review_actions()[0]

    result = HumanReviewGateway.create().decide_action(
        state=state,
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
        rationale="The action is bounded to the allowed test runner.",
    )

    updated = result.state.actions.require_action(action.action_id.value)

    assert result.before_snapshot.stage is RunStage.HUMAN_REVIEW
    assert updated.allows_execution() is True
    assert updated.requires_human_review() is False
    assert result.next_snapshot().stage is RunStage.EXECUTION_PLANNING
    assert result.receipt.changed_state() is True
    assert result.receipt.changed_action() is True


def test_human_review_gateway_rejects_action_and_keeps_review_blocker() -> None:
    state = _human_review_state()
    action = state.actions.human_review_actions()[0]

    result = HumanReviewGateway.create().decide_action(
        state=state,
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.REJECTED,
        rationale="The action is not acceptable under the current boundary.",
    )

    updated = result.state.actions.require_action(action.action_id.value)

    assert updated.blocks_progress() is True
    assert updated.requires_human_review() is False
    assert result.next_snapshot().stage is RunStage.HUMAN_REVIEW
    assert result.receipt.changed_state() is True
    assert result.receipt.changed_action() is True


def test_human_review_gateway_defers_action_and_keeps_action_unchanged() -> None:
    state = _human_review_state()
    action = state.actions.human_review_actions()[0]

    result = HumanReviewGateway.create().decide_action(
        state=state,
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.DEFERRED,
        rationale="More information is required before approval.",
    )

    updated = result.state.actions.require_action(action.action_id.value)

    assert updated == action
    assert result.next_snapshot().stage is RunStage.HUMAN_REVIEW
    assert result.receipt.changed_state() is True
    assert result.receipt.changed_action() is False


def test_human_review_gateway_rejects_when_stage_is_not_human_review() -> None:
    with pytest.raises(
        FoundationError,
        match="expected human_review but observed proposal_intake",
    ):
        HumanReviewGateway.create().decide_action(
            state=_state(),
            action_id="missing-action",
            reviewer="Bryce Lovell",
            status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
            rationale="Not reachable.",
        )


def test_human_review_gateway_rejects_non_review_action() -> None:
    action = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.SALLY,
        description="Run tests.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload(
            {"proposal_action": "run tests"},
        ),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )
    human_state = _human_review_state().with_action(action)

    with pytest.raises(FoundationError, match="not waiting for human review"):
        HumanReviewGateway.create().decide_action(
            state=human_state,
            action_id=action.action_id.value,
            reviewer="Bryce Lovell",
            status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
            rationale="Wrong target.",
        )


def test_human_review_submission_receipt_rejects_invalid_digest_algorithm() -> None:
    good = DigestRecord.from_payload({"record": "human-review-submission"})
    bad = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="expected digest algorithm sha256"):
        HumanReviewSubmissionReceipt.create(
            before_state_digest=good,
            after_state_digest=good,
            before_action_digest=good,
            after_action_digest=good,
            gate_decision_digest=good,
            human_decision_digest=bad,
            status=HumanReviewDecisionStatus.DEFERRED,
            detail="Invalid receipt.",
        )


def test_human_review_submission_result_payload_and_digest_are_stable() -> None:
    state = _human_review_state()
    action = state.actions.human_review_actions()[0]

    first = HumanReviewGateway.create().decide_action(
        state=state,
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
        rationale="The action is bounded to the allowed test runner.",
    )
    second = HumanReviewGateway.create().decide_action(
        state=state,
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
        rationale="The action is bounded to the allowed test runner.",
    )

    payload = first.to_payload()

    assert payload["before_stage"] == RunStage.HUMAN_REVIEW.value
    assert payload["next_stage"] == RunStage.EXECUTION_PLANNING.value
    assert payload["decision_status"] == (
        HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION.value
    )
    assert first.digest() == second.digest()
    assert first.receipt.digest() == second.receipt.digest()
