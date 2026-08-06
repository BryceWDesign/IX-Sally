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
from ix_sally.human_review_decision_coordinator import HumanReviewDecisionCoordinator
from ix_sally.human_review_decision_ledger import HumanReviewDecisionLedger
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_resume import (
    HumanReviewResumeCertificate,
    HumanReviewResumeCoordinator,
    HumanReviewResumeResult,
)
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Certify human-review resume.",
        mode=AutonomyMode.TEST,
        max_cycles=2,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action() -> BoundedActionRecord:
    action = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.SALLY,
        description="Run human-boundary verification.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload(
            {"proposal_action": "human boundary verification"},
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


def _cleared_assessment_and_state() -> tuple[HumanReviewClearanceAssessment, NinefoldRunState]:
    state = _state().with_action(_review_action())
    action = state.actions.human_review_actions()[0]
    bundle = HumanReviewBundleAssembler.create().assemble(state=state)
    decision = HumanReviewDecisionCoordinator.create().decide_action(
        state=state,
        ledger=HumanReviewDecisionLedger.create(()),
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
        rationale="The bounded action is approved for execution.",
    )
    assessment = HumanReviewClearanceAssessment.from_bundle(
        bundle=bundle,
        decision_ledger=decision.after_ledger,
    )

    assert assessment.cleared_to_resume() is True

    return assessment, decision.state


def test_resume_coordinator_certifies_cleared_post_decision_state() -> None:
    assessment, resumed_state = _cleared_assessment_and_state()

    result = HumanReviewResumeCoordinator().certify(
        assessment=assessment,
        resumed_state=resumed_state,
    )

    assert result.cleared_to_resume() is True
    assert result.next_stage() is RunStage.EXECUTION_PLANNING
    assert result.certificate.resumed_stage is RunStage.EXECUTION_PLANNING
    assert result.certificate.reviewed_state_digest == assessment.bundle.snapshot.state_digest
    assert result.certificate.resumed_state_digest == resumed_state.digest()


def test_resume_coordinator_rejects_pending_clearance() -> None:
    state = _state().with_action(_review_action())
    bundle = HumanReviewBundleAssembler.create().assemble(state=state)
    assessment = HumanReviewClearanceAssessment.from_bundle(
        bundle=bundle,
        decision_ledger=HumanReviewDecisionLedger.create(()),
    )

    with pytest.raises(FoundationError, match="not cleared to resume"):
        HumanReviewResumeCoordinator().certify(
            assessment=assessment,
            resumed_state=state,
        )


def test_resume_coordinator_rejects_same_reviewed_state() -> None:
    state = _state().with_action(_review_action())
    action = state.actions.human_review_actions()[0]
    bundle = HumanReviewBundleAssembler.create().assemble(state=state)
    decision = HumanReviewDecisionCoordinator.create().decide_action(
        state=state,
        ledger=HumanReviewDecisionLedger.create(()),
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
        rationale="The bounded action is approved for execution.",
    )
    assessment = HumanReviewClearanceAssessment.from_bundle(
        bundle=bundle,
        decision_ledger=decision.after_ledger,
    )

    with pytest.raises(FoundationError, match="requires a post-decision run state"):
        HumanReviewResumeCoordinator().certify(
            assessment=assessment,
            resumed_state=state,
        )


def test_resume_certificate_rejects_human_review_stage() -> None:
    digest = DigestRecord.from_payload({"record": "resume-certificate"})

    with pytest.raises(FoundationError, match="cannot resume to human_review"):
        HumanReviewResumeCertificate.create(
            reviewed_state_digest=digest,
            resumed_state_digest=digest,
            bundle_digest=digest,
            decision_ledger_digest=digest,
            clearance_report_digest=digest,
            resumed_snapshot_digest=digest,
            resumed_stage=RunStage.HUMAN_REVIEW,
            authority_note="Human authority required.",
            rationale="Invalid resume stage.",
        )


def test_resume_result_rejects_mismatched_certificate_state() -> None:
    assessment, resumed_state = _cleared_assessment_and_state()
    digest = DigestRecord.from_payload({"record": "wrong-resume"})
    certificate = HumanReviewResumeCertificate.create(
        reviewed_state_digest=assessment.bundle.snapshot.state_digest,
        resumed_state_digest=digest,
        bundle_digest=assessment.bundle.digest(),
        decision_ledger_digest=assessment.decision_ledger.digest(),
        clearance_report_digest=assessment.clearance_report.digest(),
        resumed_snapshot_digest=DigestRecord.from_payload({"snapshot": "wrong"}),
        resumed_stage=RunStage.EXECUTION_PLANNING,
        authority_note=assessment.bundle.packet.authority_note,
        rationale="Invalid certificate.",
    )

    with pytest.raises(FoundationError, match="resumed state mismatch"):
        HumanReviewResumeResult.create(
            assessment=assessment,
            resumed_state=resumed_state,
            certificate=certificate,
        )


def test_resume_result_payload_and_digest_are_stable() -> None:
    assessment, resumed_state = _cleared_assessment_and_state()

    first = HumanReviewResumeCoordinator().certify(
        assessment=assessment,
        resumed_state=resumed_state,
    )
    second = HumanReviewResumeCoordinator().certify(
        assessment=assessment,
        resumed_state=resumed_state,
    )

    payload = first.to_payload()

    assert payload["next_stage"] == RunStage.EXECUTION_PLANNING.value
    assert payload["cleared_to_resume"] is True
    assert first.digest() == second.digest()
    assert first.certificate.digest() == second.certificate.digest()
