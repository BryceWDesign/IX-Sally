from __future__ import annotations

import pytest

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_bundle import HumanReviewBundleAssembler
from ix_sally.human_review_clearance import HumanReviewClearanceAssessment
from ix_sally.human_review_control_plane import HumanReviewControlPlaneState
from ix_sally.human_review_control_plane_coordinator import (
    HumanReviewControlPlaneCoordinator,
    HumanReviewControlPlaneOperationKind,
    HumanReviewControlPlaneOperationReceipt,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Coordinate human-review control-plane operations.",
        mode=AutonomyMode.TEST,
        max_cycles=2,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(description: str = "Run human-boundary verification.") -> BoundedActionRecord:
    action = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.SALLY,
        description=description,
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload(
            {"proposal_action": description},
        ),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=True,
    )
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED,
        rationale="Human boundary is required.",
        human_review_note="Reviewer must approve the bounded action.",
    )
    return action.with_authority_decision(decision)


def test_control_plane_coordinator_records_handoff_operation() -> None:
    run_state = _state().with_action(_review_action())
    control_plane = HumanReviewControlPlaneState.create()

    result = HumanReviewControlPlaneCoordinator.create().record_handoff(
        run_state=run_state,
        control_plane=control_plane,
    )

    assert result.operation_kind() is HumanReviewControlPlaneOperationKind.HANDOFF_RECORDED
    assert result.changed_control_plane() is True
    assert result.after_control_plane.handoff_count() == 1
    assert result.after_control_plane.decision_count() == 0
    assert result.after_control_plane.resume_count() == 0
    assert result.require_handoff_result().target_count() == 1


def test_control_plane_coordinator_records_action_decision_operation() -> None:
    run_state = _state().with_action(_review_action())
    action = run_state.actions.human_review_actions()[0]
    control_plane = HumanReviewControlPlaneState.create()

    result = HumanReviewControlPlaneCoordinator.create().record_action_decision(
        run_state=run_state,
        control_plane=control_plane,
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
        rationale="The bounded action is approved for execution.",
    )

    assert result.operation_kind() is HumanReviewControlPlaneOperationKind.DECISION_RECORDED
    assert result.changed_control_plane() is True
    assert result.after_control_plane.handoff_count() == 0
    assert result.after_control_plane.decision_count() == 1
    assert result.after_control_plane.resume_count() == 0
    assert result.require_decision_result().approved_target() is True


def test_control_plane_coordinator_records_resume_operation() -> None:
    run_state = _state().with_action(_review_action())
    action = run_state.actions.human_review_actions()[0]
    coordinator = HumanReviewControlPlaneCoordinator.create()
    control_plane = HumanReviewControlPlaneState.create()
    handoff = coordinator.record_handoff(
        run_state=run_state,
        control_plane=control_plane,
    )
    decision = coordinator.record_action_decision(
        run_state=run_state,
        control_plane=handoff.after_control_plane,
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
        rationale="The bounded action is approved for execution.",
    )
    bundle = HumanReviewBundleAssembler.create().assemble(state=run_state)
    assessment = HumanReviewClearanceAssessment.from_bundle(
        bundle=bundle,
        decision_ledger=decision.after_control_plane.decision_ledger,
    )

    resume = coordinator.record_resume(
        assessment=assessment,
        resumed_state=decision.require_decision_result().state,
        control_plane=decision.after_control_plane,
    )

    assert resume.operation_kind() is HumanReviewControlPlaneOperationKind.RESUME_RECORDED
    assert resume.changed_control_plane() is True
    assert resume.after_control_plane.handoff_count() == 1
    assert resume.after_control_plane.decision_count() == 1
    assert resume.after_control_plane.resume_count() == 1
    assert resume.require_resume_result().next_stage() is RunStage.EXECUTION_PLANNING


def test_control_plane_operation_result_requires_matching_operation_payload() -> None:
    run_state = _state().with_action(_review_action())
    handoff = HumanReviewControlPlaneCoordinator.create().record_handoff(
        run_state=run_state,
        control_plane=HumanReviewControlPlaneState.create(),
    )

    with pytest.raises(FoundationError, match="has no decision result"):
        handoff.require_decision_result()

    with pytest.raises(FoundationError, match="has no resume result"):
        handoff.require_resume_result()


def test_control_plane_operation_receipt_rejects_negative_counts() -> None:
    digest = DigestRecord.from_payload({"record": "control-plane-operation"})

    with pytest.raises(FoundationError, match="handoff_count must not be negative"):
        HumanReviewControlPlaneOperationReceipt.create(
            operation_kind=HumanReviewControlPlaneOperationKind.HANDOFF_RECORDED,
            before_control_plane_digest=digest,
            after_control_plane_digest=digest,
            operation_digest=digest,
            handoff_count=-1,
            decision_count=0,
            resume_count=0,
        )


def test_control_plane_operation_result_payload_and_digest_are_stable() -> None:
    run_state = _state().with_action(_review_action())
    control_plane = HumanReviewControlPlaneState.create()

    first = HumanReviewControlPlaneCoordinator.create().record_handoff(
        run_state=run_state,
        control_plane=control_plane,
    )
    second = HumanReviewControlPlaneCoordinator.create().record_handoff(
        run_state=run_state,
        control_plane=control_plane,
    )

    payload = first.to_payload()

    assert payload["operation_kind"] == (
        HumanReviewControlPlaneOperationKind.HANDOFF_RECORDED.value
    )
    assert payload["handoff_count"] == 1
    assert payload["decision_count"] == 0
    assert payload["resume_count"] == 0
    assert payload["changed_control_plane"] is True
    assert first.digest() == second.digest()
    assert first.receipt.digest() == second.receipt.digest()
