

from __future__ import annotations

import pytest
from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_reentry import HumanReviewReentryRunner, HumanReviewReentryStatus
from ix_sally.human_review_reentry_ledger import (
    HumanReviewReentryLedger,
    HumanReviewReentryLedgerEntry,
)
from ix_sally.human_review_workflow import HumanReviewWorkflowKit
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state(max_cycles: int = 3) -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Ledger human-review reentry runs.",
        mode=AutonomyMode.TEST,
        max_cycles=max_cycles,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(description: str = "Run post-review verification.") -> BoundedActionRecord:
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
        rationale="Human boundary approval is required before the tool run.",
        human_review_note="Reviewer must approve the bounded tool action.",
    )
    return action.with_authority_decision(decision)


def _resume_operation(description: str = "Run post-review verification."):
    run_state = _state().with_action(_review_action(description))
    action = run_state.actions.human_review_actions()[0]
    kit = HumanReviewWorkflowKit.create()
    handoff = kit.open_handoff(run_state=run_state)
    decision = kit.record_action_decision(
        run_state=run_state,
        control_plane=handoff.control_plane,
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
        rationale="The bounded action is approved for execution.",
    )
    clearance = kit.assess_clearance(
        run_state=decision.run_state,
        control_plane=decision.control_plane,
        handoff=handoff.require_handoff(),
    )
    return kit.record_resume(clearance=clearance)


def _reentry_result(
    description: str = "Run post-review verification.",
    max_steps: int = 3,
):
    return HumanReviewReentryRunner.create().resume_until_stop(
        resume_operation=_resume_operation(description),
        max_steps=max_steps,
    )


def test_human_review_reentry_ledger_entry_records_reentry_result() -> None:
    result = _reentry_result()

    entry = HumanReviewReentryLedgerEntry.from_result(sequence=1, result=result)

    assert entry.sequence == 1
    assert entry.reentry_receipt_digest == result.receipt.digest()
    assert entry.resume_certificate_digest == result.receipt.resume_certificate_digest
    assert entry.after_state_digest == result.state.digest()
    assert entry.status is HumanReviewReentryStatus.WAITING_FOR_EXTERNAL_INPUT
    assert entry.final_stage is RunStage.FORGE_RESULT_PROCESSING
    assert entry.changed_state() is True
    assert entry.stopped_for_external_input() is True


def test_human_review_reentry_ledger_appends_result_at_next_sequence() -> None:
    result = _reentry_result()
    ledger = HumanReviewReentryLedger.create(())

    updated = ledger.append_result(result)

    latest = updated.latest()

    assert latest is not None
    assert updated.next_sequence() == 2
    assert latest.reentry_receipt_digest == result.receipt.digest()
    assert updated.changed_entries() == (latest,)
    assert updated.external_input_entries() == (latest,)
    assert updated.entries_by_status(HumanReviewReentryStatus.WAITING_FOR_EXTERNAL_INPUT) == (
        latest,
    )
    assert updated.entries_for_stage(RunStage.FORGE_RESULT_PROCESSING) == (latest,)


def test_human_review_reentry_ledger_rejects_duplicate_reentry_receipt_digest() -> None:
    result = _reentry_result()
    first = HumanReviewReentryLedgerEntry.from_result(sequence=1, result=result)
    duplicate = HumanReviewReentryLedgerEntry.from_result(sequence=2, result=result)

    with pytest.raises(
        FoundationError,
        match="duplicate human-review reentry receipt digest",
    ):
        HumanReviewReentryLedger.create((first, duplicate))


def test_human_review_reentry_ledger_rejects_duplicate_sequence() -> None:
    first = HumanReviewReentryLedgerEntry.from_result(
        sequence=1,
        result=_reentry_result("Run first post-review verification."),
    )
    second = HumanReviewReentryLedgerEntry.from_result(
        sequence=1,
        result=_reentry_result("Run second post-review verification."),
    )

    with pytest.raises(
        FoundationError,
        match="duplicate human-review reentry ledger sequence",
    ):
        HumanReviewReentryLedger.create((first, second))


def test_human_review_reentry_ledger_entry_rejects_invalid_digest_algorithm() -> None:
    result = _reentry_result(max_steps=1)
    bad_digest = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="expected digest algorithm sha256"):
        HumanReviewReentryLedgerEntry.create(
            sequence=1,
            reentry_receipt_digest=bad_digest,
            resume_operation_digest=result.receipt.resume_operation_digest,
            resume_certificate_digest=result.receipt.resume_certificate_digest,
            control_plane_digest=result.receipt.control_plane_digest,
            before_state_digest=result.receipt.before_state_digest,
            after_state_digest=result.receipt.after_state_digest,
            loop_digest=result.receipt.loop_digest,
            final_stage=result.receipt.final_stage,
            stop_reason=result.receipt.stop_reason,
            executed_steps=result.receipt.executed_steps,
            status=result.receipt.status,
        )


def test_human_review_reentry_ledger_entry_rejects_negative_executed_steps() -> None:
    result = _reentry_result(max_steps=1)

    with pytest.raises(FoundationError, match="executed_steps must not be negative"):
        HumanReviewReentryLedgerEntry.create(
            sequence=1,
            reentry_receipt_digest=result.receipt.digest(),
            resume_operation_digest=result.receipt.resume_operation_digest,
            resume_certificate_digest=result.receipt.resume_certificate_digest,
            control_plane_digest=result.receipt.control_plane_digest,
            before_state_digest=result.receipt.before_state_digest,
            after_state_digest=result.receipt.after_state_digest,
            loop_digest=result.receipt.loop_digest,
            final_stage=result.receipt.final_stage,
            stop_reason=result.receipt.stop_reason,
            executed_steps=-1,
            status=result.receipt.status,
        )


def test_human_review_reentry_ledger_payload_and_digest_are_stable() -> None:
    result = _reentry_result()

    first = HumanReviewReentryLedger.create(()).append_result(result)
    second = HumanReviewReentryLedger.create(()).append_result(result)

    payload = first.to_payload()
    latest = first.latest()

    assert latest is not None
    assert payload["entry_count"] == 1
    assert payload["next_sequence"] == 2
    assert payload["latest_entry_digest"] == latest.digest().value
    assert payload["changed_entry_count"] == 1
    assert payload["external_input_entry_count"] == 1
    assert payload["waiting_entry_count"] == 1
    assert payload["forge_result_processing_entry_count"] == 1
    assert first.digest() == second.digest()
