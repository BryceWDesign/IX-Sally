

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
from ix_sally.human_review_resume_coordination import (
    HumanReviewResumeCoordinationReceipt,
    HumanReviewResumeLedgerCoordinator,
)
from ix_sally.human_review_resume_ledger import HumanReviewResumeLedger
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Coordinate human-review resume certification.",
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


def _cleared_parts(
    description: str = "Run human-boundary verification.",
) -> tuple[HumanReviewClearanceAssessment, NinefoldRunState]:
    state = _state().with_action(_review_action(description))
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


def test_resume_ledger_coordinator_certifies_and_records_resume() -> None:
    assessment, resumed_state = _cleared_parts()
    ledger = HumanReviewResumeLedger.create(())

    result = HumanReviewResumeLedgerCoordinator.create().certify_and_record(
        assessment=assessment,
        resumed_state=resumed_state,
        ledger=ledger,
    )

    assert result.before_ledger == ledger
    assert result.after_ledger.next_sequence() == 2
    assert result.latest_entry() == result.ledger_entry
    assert result.ledger_entry.certificate_digest == result.resume_result.certificate.digest()
    assert result.next_stage() is RunStage.EXECUTION_PLANNING
    assert result.cleared_to_resume() is True
    assert result.receipt.changed_ledger() is True


def test_resume_ledger_coordinator_preserves_custom_rationale() -> None:
    assessment, resumed_state = _cleared_parts()

    result = HumanReviewResumeLedgerCoordinator.create().certify_and_record(
        assessment=assessment,
        resumed_state=resumed_state,
        ledger=HumanReviewResumeLedger.create(()),
        rationale="Operator-approved action may now enter execution planning.",
    )

    assert result.resume_result.certificate.rationale == (
        "Operator-approved action may now enter execution planning."
    )
    assert result.ledger_entry.rationale == (
        "Operator-approved action may now enter execution planning."
    )
    assert result.receipt.rationale == (
        "Operator-approved action may now enter execution planning."
    )


def test_resume_ledger_coordinator_rejects_uncleared_assessment() -> None:
    state = _state().with_action(_review_action())
    bundle = HumanReviewBundleAssembler.create().assemble(state=state)
    assessment = HumanReviewClearanceAssessment.from_bundle(
        bundle=bundle,
        decision_ledger=HumanReviewDecisionLedger.create(()),
    )

    with pytest.raises(FoundationError, match="not cleared to resume"):
        HumanReviewResumeLedgerCoordinator.create().certify_and_record(
            assessment=assessment,
            resumed_state=state,
            ledger=HumanReviewResumeLedger.create(()),
        )


def test_resume_ledger_coordinator_rejects_duplicate_certificate_on_same_ledger() -> None:
    assessment, resumed_state = _cleared_parts()
    coordinator = HumanReviewResumeLedgerCoordinator.create()
    first = coordinator.certify_and_record(
        assessment=assessment,
        resumed_state=resumed_state,
        ledger=HumanReviewResumeLedger.create(()),
    )

    with pytest.raises(
        FoundationError,
        match="duplicate human-review resume certificate digest",
    ):
        coordinator.certify_and_record(
            assessment=assessment,
            resumed_state=resumed_state,
            ledger=first.after_ledger,
        )


def test_resume_coordination_receipt_rejects_human_review_resume_stage() -> None:
    digest = DigestRecord.from_payload({"record": "resume-coordination"})

    with pytest.raises(FoundationError, match="cannot resume to human_review"):
        HumanReviewResumeCoordinationReceipt.create(
            before_ledger_digest=digest,
            after_ledger_digest=digest,
            resume_result_digest=digest,
            ledger_entry_digest=digest,
            certificate_digest=digest,
            reviewed_state_digest=digest,
            resumed_state_digest=digest,
            resumed_stage=RunStage.HUMAN_REVIEW,
            authority_note="Human authority required.",
            rationale="Invalid resume coordination.",
        )


def test_resume_coordination_receipt_rejects_invalid_digest_algorithm() -> None:
    digest = DigestRecord.from_payload({"record": "resume-coordination"})
    bad_digest = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="expected digest algorithm sha256"):
        HumanReviewResumeCoordinationReceipt.create(
            before_ledger_digest=bad_digest,
            after_ledger_digest=digest,
            resume_result_digest=digest,
            ledger_entry_digest=digest,
            certificate_digest=digest,
            reviewed_state_digest=digest,
            resumed_state_digest=digest,
            resumed_stage=RunStage.EXECUTION_PLANNING,
            authority_note="Human authority required.",
            rationale="Invalid digest algorithm.",
        )


def test_resume_coordination_result_payload_and_digest_are_stable() -> None:
    assessment, resumed_state = _cleared_parts()
    ledger = HumanReviewResumeLedger.create(())

    first = HumanReviewResumeLedgerCoordinator.create().certify_and_record(
        assessment=assessment,
        resumed_state=resumed_state,
        ledger=ledger,
    )
    second = HumanReviewResumeLedgerCoordinator.create().certify_and_record(
        assessment=assessment,
        resumed_state=resumed_state,
        ledger=ledger,
    )

    payload = first.to_payload()

    assert payload["next_stage"] == RunStage.EXECUTION_PLANNING.value
    assert payload["changed_ledger"] is True
    assert payload["cleared_to_resume"] is True
    assert first.digest() == second.digest()
    assert first.receipt.digest() == second.receipt.digest()
