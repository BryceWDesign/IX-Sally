

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
from ix_sally.human_review_resume import HumanReviewResumeCoordinator
from ix_sally.human_review_resume_ledger import (
    HumanReviewResumeLedger,
    HumanReviewResumeLedgerEntry,
)
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Ledger human-review resume certificates.",
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


def _resume_result(description: str = "Run human-boundary verification."):
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

    return HumanReviewResumeCoordinator().certify(
        assessment=assessment,
        resumed_state=decision.state,
    )


def test_human_review_resume_ledger_entry_records_resume_result() -> None:
    result = _resume_result()

    entry = HumanReviewResumeLedgerEntry.from_result(sequence=1, result=result)

    assert entry.sequence == 1
    assert entry.certificate_digest == result.certificate.digest()
    assert entry.assessment_digest == result.assessment.digest()
    assert entry.clearance_report_digest == result.assessment.clearance_report.digest()
    assert entry.resumed_state_digest == result.resumed_state.digest()
    assert entry.resumed_stage is RunStage.EXECUTION_PLANNING
    assert entry.cleared_to_resume() is True


def test_human_review_resume_ledger_appends_result_at_next_sequence() -> None:
    result = _resume_result()
    ledger = HumanReviewResumeLedger.create(())

    updated = ledger.append_result(result)

    latest = updated.latest()

    assert latest is not None
    assert updated.next_sequence() == 2
    assert latest.certificate_digest == result.certificate.digest()
    assert updated.cleared_entries() == (latest,)
    assert updated.entries_for_stage(RunStage.EXECUTION_PLANNING) == (latest,)


def test_human_review_resume_ledger_rejects_duplicate_certificate_digest() -> None:
    result = _resume_result()
    first = HumanReviewResumeLedgerEntry.from_result(sequence=1, result=result)
    duplicate = HumanReviewResumeLedgerEntry.from_result(sequence=2, result=result)

    with pytest.raises(
        FoundationError,
        match="duplicate human-review resume certificate digest",
    ):
        HumanReviewResumeLedger.create((first, duplicate))


def test_human_review_resume_ledger_rejects_duplicate_sequence() -> None:
    first = HumanReviewResumeLedgerEntry.from_result(
        sequence=1,
        result=_resume_result("Run first human-boundary verification."),
    )
    second = HumanReviewResumeLedgerEntry.from_result(
        sequence=1,
        result=_resume_result("Run second human-boundary verification."),
    )

    with pytest.raises(
        FoundationError,
        match="duplicate human-review resume ledger sequence",
    ):
        HumanReviewResumeLedger.create((first, second))


def test_human_review_resume_ledger_entry_rejects_human_review_resume_stage() -> None:
    result = _resume_result()

    with pytest.raises(FoundationError, match="cannot resume to human_review"):
        HumanReviewResumeLedgerEntry.create(
            sequence=1,
            certificate_digest=result.certificate.digest(),
            assessment_digest=result.assessment.digest(),
            clearance_report_digest=result.assessment.clearance_report.digest(),
            reviewed_state_digest=result.assessment.bundle.snapshot.state_digest,
            resumed_state_digest=result.resumed_state.digest(),
            resumed_snapshot_digest=result.resumed_snapshot.digest(),
            resumed_stage=RunStage.HUMAN_REVIEW,
            authority_note=result.certificate.authority_note,
            rationale=result.certificate.rationale,
        )


def test_human_review_resume_ledger_entry_rejects_invalid_digest_algorithm() -> None:
    result = _resume_result()
    bad_digest = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="expected digest algorithm sha256"):
        HumanReviewResumeLedgerEntry.create(
            sequence=1,
            certificate_digest=bad_digest,
            assessment_digest=result.assessment.digest(),
            clearance_report_digest=result.assessment.clearance_report.digest(),
            reviewed_state_digest=result.assessment.bundle.snapshot.state_digest,
            resumed_state_digest=result.resumed_state.digest(),
            resumed_snapshot_digest=result.resumed_snapshot.digest(),
            resumed_stage=result.next_stage(),
            authority_note=result.certificate.authority_note,
            rationale=result.certificate.rationale,
        )


def test_human_review_resume_ledger_payload_and_digest_are_stable() -> None:
    result = _resume_result()

    first = HumanReviewResumeLedger.create(()).append_result(result)
    second = HumanReviewResumeLedger.create(()).append_result(result)

    payload = first.to_payload()
    latest = first.latest()

    assert latest is not None
    assert payload["entry_count"] == 1
    assert payload["next_sequence"] == 2
    assert payload["latest_entry_digest"] == latest.digest().value
    assert payload["cleared_entry_count"] == 1
    assert payload["execution_planning_resume_count"] == 1
    assert first.digest() == second.digest()
