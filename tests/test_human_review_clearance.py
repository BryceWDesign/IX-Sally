from __future__ import annotations

import pytest

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.evidence_support import EvidenceSupportFinding, EvidenceSupportStatus
from ix_sally.foundation import FoundationError
from ix_sally.human_review_bundle import HumanReviewBundleAssembler
from ix_sally.human_review_clearance import (
    HumanReviewClearanceAssessment,
    HumanReviewClearanceReport,
    HumanReviewClearanceStatus,
)
from ix_sally.human_review_decision_coordinator import HumanReviewDecisionCoordinator
from ix_sally.human_review_decision_ledger import HumanReviewDecisionLedger
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Assess human-review clearance.",
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


def _denied_action() -> BoundedActionRecord:
    action = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.SALLY,
        description="Run disallowed verification.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload(
            {"proposal_action": "denied"},
        ),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.DENIED,
        rationale="Authority denied this action.",
        contract_note="Contract does not permit this action.",
    )
    return action.with_authority_decision(decision)


def _unsupported_finding() -> EvidenceSupportFinding:
    return EvidenceSupportFinding.create(
        cycle=1,
        claim_digest=DigestRecord.from_payload({"claim": "unsupported"}),
        status=EvidenceSupportStatus.UNSUPPORTED,
        rationale="No recorded evidence supports the claim.",
    )


def _assessment_for_decision(status: HumanReviewDecisionStatus) -> HumanReviewClearanceAssessment:
    state = _state().with_action(_review_action())
    action = state.actions.human_review_actions()[0]
    bundle = HumanReviewBundleAssembler.create().assemble(state=state)
    decision = HumanReviewDecisionCoordinator.create().decide_action(
        state=state,
        ledger=HumanReviewDecisionLedger.create(()),
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=status,
        rationale="Operator decision for clearance assessment.",
    )

    return HumanReviewClearanceAssessment.from_bundle(
        bundle=bundle,
        decision_ledger=decision.after_ledger,
    )


def test_clearance_report_marks_pending_gateway_decision() -> None:
    state = _state().with_action(_review_action())
    bundle = HumanReviewBundleAssembler.create().assemble(state=state)

    assessment = HumanReviewClearanceAssessment.from_bundle(
        bundle=bundle,
        decision_ledger=HumanReviewDecisionLedger.create(()),
    )

    assert assessment.clearance_report.status is (
        HumanReviewClearanceStatus.PENDING_GATEWAY_DECISION
    )
    assert assessment.cleared_to_resume() is False
    assert assessment.requires_operator_attention() is True
    assert assessment.clearance_report.pending_decision_count == 1


def test_clearance_report_marks_approved_gateway_decision_as_cleared() -> None:
    assessment = _assessment_for_decision(
        HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
    )

    assert assessment.clearance_report.status is HumanReviewClearanceStatus.CLEARED_TO_RESUME
    assert assessment.cleared_to_resume() is True
    assert assessment.requires_operator_attention() is False
    assert assessment.clearance_report.approved_decision_count == 1
    assert assessment.clearance_report.has_blocking_decision() is False


def test_clearance_report_marks_deferred_gateway_decision_open() -> None:
    assessment = _assessment_for_decision(HumanReviewDecisionStatus.DEFERRED)

    assert assessment.clearance_report.status is (HumanReviewClearanceStatus.DEFERRED_DECISION_OPEN)
    assert assessment.cleared_to_resume() is False
    assert assessment.clearance_report.deferred_decision_count == 1
    assert assessment.clearance_report.has_blocking_decision() is True


def test_clearance_report_marks_rejected_gateway_decision_blocked() -> None:
    assessment = _assessment_for_decision(HumanReviewDecisionStatus.REJECTED)

    assert assessment.clearance_report.status is (
        HumanReviewClearanceStatus.REJECTED_DECISION_BLOCKED
    )
    assert assessment.cleared_to_resume() is False
    assert assessment.clearance_report.rejected_decision_count == 1
    assert assessment.clearance_report.has_blocking_decision() is True


def test_clearance_report_marks_manual_investigation_open() -> None:
    state = _state().with_evidence_support_finding(_unsupported_finding())
    bundle = HumanReviewBundleAssembler.create().assemble(state=state)

    assessment = HumanReviewClearanceAssessment.from_bundle(
        bundle=bundle,
        decision_ledger=HumanReviewDecisionLedger.create(()),
    )

    assert assessment.clearance_report.status is (
        HumanReviewClearanceStatus.MANUAL_INVESTIGATION_OPEN
    )
    assert assessment.cleared_to_resume() is False
    assert assessment.clearance_report.manual_investigation_count == 1


def test_clearance_report_marks_blocker_acknowledgment_open() -> None:
    state = _state().with_action(_denied_action())
    bundle = HumanReviewBundleAssembler.create().assemble(state=state)

    assessment = HumanReviewClearanceAssessment.from_bundle(
        bundle=bundle,
        decision_ledger=HumanReviewDecisionLedger.create(()),
    )

    assert assessment.clearance_report.status is (
        HumanReviewClearanceStatus.BLOCKER_ACKNOWLEDGMENT_OPEN
    )
    assert assessment.cleared_to_resume() is False
    assert assessment.clearance_report.blocker_acknowledgment_count == 1


def test_clearance_report_rejects_mismatched_counts() -> None:
    digest = DigestRecord.from_payload({"record": "clearance-report"})

    with pytest.raises(FoundationError, match="surfaced counts must equal"):
        HumanReviewClearanceReport.create(
            bundle_digest=digest,
            decision_ledger_digest=digest,
            resolution_audit_digest=digest,
            state_digest=digest,
            status=HumanReviewClearanceStatus.CLEARED_TO_RESUME,
            rationale="Invalid report.",
            card_count=2,
            resolved_count=1,
            pending_decision_count=0,
            approved_decision_count=1,
            rejected_decision_count=0,
            deferred_decision_count=0,
            manual_investigation_count=0,
            blocker_acknowledgment_count=0,
        )


def test_clearance_assessment_payload_and_digest_are_stable() -> None:
    first = _assessment_for_decision(HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION)
    second = _assessment_for_decision(HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION)

    payload = first.to_payload()

    assert payload["status"] == HumanReviewClearanceStatus.CLEARED_TO_RESUME.value
    assert payload["cleared_to_resume"] is True
    assert payload["requires_operator_attention"] is False
    assert first.digest() == second.digest()
    assert first.clearance_report.digest() == second.clearance_report.digest()
