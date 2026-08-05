

from __future__ import annotations

import pytest
from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_bundle import HumanReviewBundleAssembler
from ix_sally.human_review_bundle_ledger import HumanReviewBundleLedger
from ix_sally.human_review_clearance import HumanReviewClearanceAssessment
from ix_sally.human_review_control_plane import (
    HumanReviewControlPlaneSnapshot,
    HumanReviewControlPlaneState,
    HumanReviewControlPlaneStatus,
)
from ix_sally.human_review_decision_coordinator import HumanReviewDecisionCoordinator
from ix_sally.human_review_decision_ledger import HumanReviewDecisionLedger
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_resume import HumanReviewResumeCoordinator
from ix_sally.human_review_resume_ledger import HumanReviewResumeLedger
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Track human-review control-plane state.",
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


def _control_state_after_handoff() -> HumanReviewControlPlaneState:
    state = _state().with_action(_review_action())
    bundle = HumanReviewBundleAssembler.create().assemble(state=state)
    handoff_ledger = HumanReviewBundleLedger.create(()).append_bundle(bundle)

    return HumanReviewControlPlaneState.create().with_handoff_ledger(handoff_ledger)


def _control_state_after_approved_decision() -> tuple[
    HumanReviewControlPlaneState,
    NinefoldRunState,
]:
    state = _state().with_action(_review_action())
    bundle = HumanReviewBundleAssembler.create().assemble(state=state)
    handoff_ledger = HumanReviewBundleLedger.create(()).append_bundle(bundle)
    action = state.actions.human_review_actions()[0]
    decision_result = HumanReviewDecisionCoordinator.create().decide_action(
        state=state,
        ledger=HumanReviewDecisionLedger.create(()),
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
        rationale="The bounded action is approved for execution.",
    )

    control_state = (
        HumanReviewControlPlaneState.create()
        .with_handoff_ledger(handoff_ledger)
        .with_decision_ledger(decision_result.after_ledger)
    )

    return control_state, decision_result.state


def test_control_plane_state_defaults_to_empty_ledgers() -> None:
    state = HumanReviewControlPlaneState.create()

    assert state.handoff_count() == 0
    assert state.decision_count() == 0
    assert state.resume_count() == 0
    assert state.has_active_handoffs() is False
    assert state.has_recorded_decisions() is False
    assert state.has_recorded_resumes() is False
    assert state.latest_handoff_digest() is None
    assert state.latest_decision_digest() is None
    assert state.latest_resume_digest() is None


def test_control_plane_state_tracks_handoff_ledger() -> None:
    state = _control_state_after_handoff()

    assert state.handoff_count() == 1
    assert state.decision_count() == 0
    assert state.resume_count() == 0
    assert state.has_active_handoffs() is True
    assert state.latest_handoff_digest() is not None


def test_control_plane_status_tracks_unresumed_approved_decision() -> None:
    state, _resumed_state = _control_state_after_approved_decision()

    status = HumanReviewControlPlaneStatus.from_state(state)

    assert status.handoff_count == 1
    assert status.decision_count == 1
    assert status.resume_count == 0
    assert status.approved_decision_count == 1
    assert status.has_unresumed_decisions() is True
    assert status.has_successful_resume() is False


def test_control_plane_status_tracks_successful_resume() -> None:
    state, resumed_state = _control_state_after_approved_decision()
    original_state = _state().with_action(_review_action())
    bundle = HumanReviewBundleAssembler.create().assemble(state=original_state)
    assessment = HumanReviewClearanceAssessment.from_bundle(
        bundle=bundle,
        decision_ledger=state.decision_ledger,
    )
    resume_result = HumanReviewResumeCoordinator().certify(
        assessment=assessment,
        resumed_state=resumed_state,
    )
    updated = state.with_resume_ledger(
        HumanReviewResumeLedger.create(()).append_result(resume_result),
    )

    status = HumanReviewControlPlaneStatus.from_state(updated)

    assert status.resume_count == 1
    assert status.cleared_resume_count == 1
    assert status.execution_planning_resume_count == 1
    assert status.has_unresumed_decisions() is False
    assert status.has_successful_resume() is True
    assert updated.latest_resume_digest() is not None


def test_control_plane_snapshot_rejects_inconsistent_status() -> None:
    state = HumanReviewControlPlaneState.create()
    handoff_state = _control_state_after_handoff()
    wrong_status = HumanReviewControlPlaneStatus.from_state(handoff_state)
    snapshot = HumanReviewControlPlaneSnapshot(state=state, status=wrong_status)

    with pytest.raises(FoundationError, match="snapshot digest mismatch"):
        snapshot.require_consistent()


def test_control_plane_snapshot_payload_and_digest_are_stable() -> None:
    state = _control_state_after_handoff()

    first = HumanReviewControlPlaneSnapshot.from_state(state)
    second = HumanReviewControlPlaneSnapshot.from_state(state)

    payload = first.to_payload()

    assert payload["status"]["handoff_count"] == 1
    assert payload["status"]["decision_count"] == 0
    assert payload["status"]["resume_count"] == 0
    assert first.digest() == second.digest()
