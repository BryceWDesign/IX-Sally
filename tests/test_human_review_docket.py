from __future__ import annotations

import pytest

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.evidence_support import EvidenceSupportFinding, EvidenceSupportStatus
from ix_sally.forge_results import ForgeResultRecord, ForgeResultStatus
from ix_sally.foundation import FoundationError
from ix_sally.human_review_docket import (
    HumanReviewDocket,
    HumanReviewDocketBuilder,
    HumanReviewDocketSeverity,
    HumanReviewDocketTarget,
    HumanReviewDocketTargetType,
)
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Assemble human-review docket.",
        mode=AutonomyMode.TEST,
        max_cycles=2,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _action() -> BoundedActionRecord:
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


def _review_action() -> BoundedActionRecord:
    action = _action()
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED,
        rationale="Human boundary is required.",
        human_review_note="Reviewer must approve the bounded action.",
    )
    return action.with_authority_decision(decision)


def _denied_action() -> BoundedActionRecord:
    action = _action()
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.DENIED,
        rationale="Authority denied by contract.",
        contract_note="Contract does not allow this action.",
    )
    return action.with_authority_decision(decision)


def test_human_review_docket_builder_collects_review_action_target() -> None:
    state = _state().with_action(_review_action())

    docket = HumanReviewDocketBuilder.create().build(state=state)

    assert docket.to_payload()["target_count"] == 1
    assert docket.to_payload()["review_required_count"] == 1
    assert docket.to_payload()["blocking_count"] == 0
    assert docket.targets[0].target_type is HumanReviewDocketTargetType.BOUNDED_ACTION
    assert docket.targets[0].severity is HumanReviewDocketSeverity.REVIEW_REQUIRED


def test_human_review_docket_builder_collects_blocking_action_target() -> None:
    state = _state().with_action(_denied_action())

    docket = HumanReviewDocketBuilder.create().build(state=state)

    assert docket.to_payload()["target_count"] == 1
    assert docket.to_payload()["review_required_count"] == 0
    assert docket.to_payload()["blocking_count"] == 1
    assert docket.targets[0].target_type is HumanReviewDocketTargetType.BOUNDED_ACTION
    assert docket.targets[0].severity is HumanReviewDocketSeverity.BLOCKER


def test_human_review_docket_builder_collects_evidence_support_target() -> None:
    finding = EvidenceSupportFinding.create(
        cycle=1,
        claim_digest=DigestRecord.from_payload({"claim": "unsupported"}),
        status=EvidenceSupportStatus.UNSUPPORTED,
        rationale="No recorded evidence supports the claim.",
    )
    state = _state().with_evidence_support_finding(finding)

    docket = HumanReviewDocketBuilder.create().build(state=state)

    assert docket.to_payload()["evidence_support_finding_count"] == 1
    assert docket.targets[0].target_type is (
        HumanReviewDocketTargetType.EVIDENCE_SUPPORT_FINDING
    )
    assert docket.targets[0].requires_decision() is True


def test_human_review_docket_builder_collects_forge_result_target() -> None:
    action = _action()
    result = ForgeResultRecord.create(
        cycle=1,
        queue_item_digest=DigestRecord.from_payload({"queue": "dispatched"}),
        action_id=action.action_id,
        action_digest=action.digest(),
        status=ForgeResultStatus.FAILED,
        summary="Forge execution failed.",
        failure_reason="The bounded verification failed.",
    )
    state = _state().with_forge_result(result)

    docket = HumanReviewDocketBuilder.create().build(state=state)

    assert docket.to_payload()["forge_result_count"] == 1
    assert docket.targets[0].target_type is HumanReviewDocketTargetType.FORGE_RESULT
    assert docket.targets[0].severity is HumanReviewDocketSeverity.REVIEW_REQUIRED


def test_human_review_docket_builder_requires_human_review_stage() -> None:
    with pytest.raises(
        FoundationError,
        match="expected human_review but observed proposal_intake",
    ):
        HumanReviewDocketBuilder.create().build(state=_state())


def test_human_review_docket_rejects_duplicate_targets() -> None:
    target = HumanReviewDocketTarget.create(
        target_type=HumanReviewDocketTargetType.BOUNDED_ACTION,
        target_id="same-target",
        cycle=1,
        target_digest=DigestRecord.from_payload({"target": "same"}),
        source_status="human_review_required",
        severity=HumanReviewDocketSeverity.REVIEW_REQUIRED,
        summary="Review target.",
        rationale="Review required.",
    )
    digest = DigestRecord.from_payload({"record": "docket"})

    with pytest.raises(FoundationError, match="duplicate human-review docket target"):
        HumanReviewDocket.create(
            state_digest=digest,
            snapshot_digest=digest,
            gate_decision_digest=digest,
            targets=(target, target),
        )


def test_human_review_docket_payload_and_digest_are_stable() -> None:
    state = _state().with_action(_review_action())

    first = HumanReviewDocketBuilder.create().build(state=state)
    second = HumanReviewDocketBuilder.create().build(state=state)

    payload = first.to_payload()

    assert payload["target_count"] == 1
    assert payload["bounded_action_count"] == 1
    assert payload["review_required_count"] == 1
    assert payload["blocking_count"] == 0
    assert first.digest() == second.digest()
