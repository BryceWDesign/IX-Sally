

from __future__ import annotations

import pytest
from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.evidence_support import EvidenceSupportFinding, EvidenceSupportStatus
from ix_sally.foundation import FoundationError
from ix_sally.human_review_bundle import (
    HumanReviewBundleAssembler,
    HumanReviewBundleReceipt,
    HumanReviewOperatorBundle,
)
from ix_sally.human_review_docket import HumanReviewDocketBuilder
from ix_sally.human_review_packets import HumanReviewPacket
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage, RunStageSnapshot
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Assemble human-review operator bundle.",
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
        description="Run a human-boundary verification step.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload(
            {"proposal_action": "human boundary action"},
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


def _unsupported_finding() -> EvidenceSupportFinding:
    return EvidenceSupportFinding.create(
        cycle=1,
        claim_digest=DigestRecord.from_payload({"claim": "unsupported"}),
        status=EvidenceSupportStatus.UNSUPPORTED,
        rationale="No recorded evidence supports the claim.",
    )


def test_human_review_bundle_assembler_builds_complete_operator_bundle() -> None:
    state = _state().with_action(_review_action())

    bundle = HumanReviewBundleAssembler.create().assemble(state=state)

    assert bundle.snapshot.stage is RunStage.HUMAN_REVIEW
    assert bundle.target_count() == 1
    assert bundle.gateway_resolvable_count() == 1
    assert bundle.manual_investigation_count() == 0
    assert bundle.blocker_acknowledgment_count() == 0
    assert bundle.receipt.requires_human_authority() is True


def test_human_review_bundle_assembler_accepts_custom_authority_note() -> None:
    state = _state().with_action(_review_action())

    bundle = HumanReviewBundleAssembler.create().assemble(
        state=state,
        authority_note="Operator approval must be explicit.",
    )

    assert bundle.packet.authority_note == "Operator approval must be explicit."
    assert bundle.receipt.authority_note == "Operator approval must be explicit."


def test_human_review_bundle_assembler_combines_gateway_and_manual_cards() -> None:
    state = _state().with_action(_review_action()).with_evidence_support_finding(
        _unsupported_finding(),
    )

    bundle = HumanReviewBundleAssembler.create().assemble(state=state)

    assert bundle.target_count() == 2
    assert bundle.gateway_resolvable_count() == 1
    assert bundle.manual_investigation_count() == 1
    assert bundle.blocker_acknowledgment_count() == 0


def test_human_review_bundle_assembler_requires_human_review_stage() -> None:
    with pytest.raises(
        FoundationError,
        match="expected human_review but observed proposal_intake",
    ):
        HumanReviewBundleAssembler.create().assemble(state=_state())


def test_human_review_bundle_receipt_rejects_mismatched_counts() -> None:
    digest = DigestRecord.from_payload({"record": "bundle-receipt"})

    with pytest.raises(FoundationError, match="surfaced card counts must equal"):
        HumanReviewBundleReceipt.create(
            state_digest=digest,
            snapshot_digest=digest,
            docket_digest=digest,
            packet_digest=digest,
            target_count=2,
            gateway_resolvable_count=1,
            manual_investigation_count=0,
            blocker_acknowledgment_count=0,
            authority_note="Human authority required.",
        )


def test_human_review_operator_bundle_rejects_mismatched_docket_reference() -> None:
    state = _state().with_action(_review_action())
    snapshot = RunStageSnapshot.from_state(state)
    docket = HumanReviewDocketBuilder.create().build(state=state)
    packet = HumanReviewPacket.from_docket(docket)
    receipt = HumanReviewBundleReceipt.create(
        state_digest=snapshot.state_digest,
        snapshot_digest=snapshot.digest(),
        docket_digest=DigestRecord.from_payload({"wrong": "docket"}),
        packet_digest=packet.digest(),
        target_count=1,
        gateway_resolvable_count=1,
        manual_investigation_count=0,
        blocker_acknowledgment_count=0,
        authority_note=packet.authority_note,
    )

    with pytest.raises(FoundationError, match="does not reference docket digest"):
        HumanReviewOperatorBundle.create(
            snapshot=snapshot,
            docket=docket,
            packet=packet,
            receipt=receipt,
        )


def test_human_review_operator_bundle_payload_and_digest_are_stable() -> None:
    state = _state().with_action(_review_action())

    first = HumanReviewBundleAssembler.create().assemble(state=state)
    second = HumanReviewBundleAssembler.create().assemble(state=state)

    payload = first.to_payload()

    assert payload["stage"] == RunStage.HUMAN_REVIEW.value
    assert payload["target_count"] == 1
    assert payload["gateway_resolvable_count"] == 1
    assert payload["requires_human_authority"] is True
    assert first.digest() == second.digest()
    assert first.receipt.digest() == second.receipt.digest()
