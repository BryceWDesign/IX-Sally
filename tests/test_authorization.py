

from __future__ import annotations

import pytest
from ix_sally.agents import AgentRole, default_agent_role_registry
from ix_sally.authorization import (
    AuthorityDecision,
    AuthorityDecisionLedger,
    AuthorityDecisionStatus,
    AuthorityRequest,
    decide_authority_request,
)
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.jurisdiction import JurisdictionGate


def _contract(
    *,
    allowed_tools: tuple[str, ...] = ("test-runner",),
    memory_writes_allowed: bool = False,
) -> AutonomyContract:
    return AutonomyContract.create(
        goal="Authorize a bounded action.",
        mode=AutonomyMode.TEST,
        max_cycles=1,
        allowed_tools=allowed_tools,
        memory_writes_allowed=memory_writes_allowed,
    )


def _gate() -> JurisdictionGate:
    return JurisdictionGate(default_agent_role_registry())


def test_authority_request_normalizes_fields_and_generates_id() -> None:
    action_digest = DigestRecord.from_payload({"action": "run tests"})
    request = AuthorityRequest.create(
        cycle=1,
        requesting_role=AgentRole.FORGE,
        action_digest=action_digest,
        requested_authority=" Tool Execution ",
        summary="  Run the bounded test command. ",
        tool_key=" Test Runner ",
        requires_tool=True,
        requires_human_boundary=False,
    )

    assert request.request_id.value == "ix-forge-1-tool-execution-run-the-bounded-test-command"
    assert request.requested_authority.value == "tool-execution"
    assert request.summary == "Run the bounded test command."
    assert request.tool_key is not None
    assert request.tool_key.value == "test-runner"
    assert request.requires_tool is True


def test_authority_request_rejects_negative_cycle() -> None:
    action_digest = DigestRecord.from_payload({"action": "run tests"})

    with pytest.raises(FoundationError, match="authority request cycle must not be negative"):
        AuthorityRequest.create(
            cycle=-1,
            requesting_role=AgentRole.FORGE,
            action_digest=action_digest,
            requested_authority="tool-execution",
            summary="Invalid cycle.",
        )


def test_tool_authority_request_requires_tool_key() -> None:
    action_digest = DigestRecord.from_payload({"action": "run tests"})

    with pytest.raises(FoundationError, match="tool authority requests require a tool key"):
        AuthorityRequest.create(
            cycle=1,
            requesting_role=AgentRole.FORGE,
            action_digest=action_digest,
            requested_authority="tool-execution",
            summary="Missing tool.",
            requires_tool=True,
        )


def test_authority_request_rejects_non_sha256_action_digest() -> None:
    action_digest = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        AuthorityRequest.create(
            cycle=1,
            requesting_role=AgentRole.FORGE,
            action_digest=action_digest,
            requested_authority="tool-execution",
            summary="Invalid digest.",
        )


def test_authority_request_payload_is_stable() -> None:
    action_digest = DigestRecord.from_payload({"action": "run tests"})
    request = AuthorityRequest.create(
        request_id=CanonicalKey.from_text("request-one", field_name="request_id"),
        cycle=1,
        requesting_role=AgentRole.FORGE,
        action_digest=action_digest,
        requested_authority="tool-execution",
        summary="Run tests.",
        tool_key="test-runner",
        requires_tool=True,
        requires_memory_write=False,
        requires_human_boundary=False,
    )

    assert request.to_payload() == {
        "request_id": "request-one",
        "cycle": 1,
        "requesting_role": "ix-forge",
        "action_digest": {
            "algorithm": "sha256",
            "value": action_digest.value,
        },
        "requested_authority": "tool-execution",
        "summary": "Run tests.",
        "tool_key": "test-runner",
        "requires_tool": True,
        "requires_memory_write": False,
        "requires_human_boundary": False,
    }


def test_authority_decision_requires_contract_note_when_denied() -> None:
    request_digest = DigestRecord.from_payload({"request": "tool"})

    with pytest.raises(FoundationError, match="denied authority decisions require"):
        AuthorityDecision.create(
            cycle=1,
            request_digest=request_digest,
            status=AuthorityDecisionStatus.DENIED,
            rationale="Denied.",
        )


def test_authority_decision_requires_human_note_when_human_review_required() -> None:
    request_digest = DigestRecord.from_payload({"request": "tool"})

    with pytest.raises(FoundationError, match="human-review authority decisions require"):
        AuthorityDecision.create(
            cycle=1,
            request_digest=request_digest,
            status=AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED,
            rationale="Human review required.",
        )


def test_authority_decision_payload_is_stable() -> None:
    request_digest = DigestRecord.from_payload({"request": "tool"})
    decision = AuthorityDecision.create(
        decision_id=CanonicalKey.from_text("decision-one", field_name="decision_id"),
        cycle=1,
        request_digest=request_digest,
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Allowed.",
    )

    assert decision.to_payload() == {
        "decision_id": "decision-one",
        "cycle": 1,
        "request_digest": {
            "algorithm": "sha256",
            "value": request_digest.value,
        },
        "status": "allowed",
        "rationale": "Allowed.",
        "jurisdiction_decision": None,
        "contract_note": None,
        "human_review_note": None,
        "allows_action": True,
        "requires_human_review": False,
        "denies_action": False,
    }


def test_decide_authority_request_allows_allowed_tool_without_human_boundary() -> None:
    action_digest = DigestRecord.from_payload({"action": "run tests"})
    request = AuthorityRequest.create(
        cycle=1,
        requesting_role=AgentRole.FORGE,
        action_digest=action_digest,
        requested_authority="tool-execution",
        summary="Run tests.",
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )

    decision = decide_authority_request(
        request=request,
        contract=_contract(),
        jurisdiction_gate=_gate(),
    )

    assert decision.status is AuthorityDecisionStatus.ALLOWED
    assert decision.allows_action() is True
    assert decision.jurisdiction_decision is not None
    assert decision.jurisdiction_decision.allowed is True


def test_decide_authority_request_denies_jurisdiction_violation() -> None:
    action_digest = DigestRecord.from_payload({"action": "judge evidence"})
    request = AuthorityRequest.create(
        cycle=1,
        requesting_role=AgentRole.SALLY,
        action_digest=action_digest,
        requested_authority="evidence-judgment",
        summary="Judge own evidence.",
        requires_human_boundary=False,
    )

    decision = decide_authority_request(
        request=request,
        contract=_contract(),
        jurisdiction_gate=_gate(),
    )

    assert decision.status is AuthorityDecisionStatus.DENIED
    assert decision.denies_action() is True
    assert decision.contract_note == "role ix-sally is prohibited from authority evidence-judgment"


def test_decide_authority_request_denies_unallowed_tool() -> None:
    action_digest = DigestRecord.from_payload({"action": "run network"})
    request = AuthorityRequest.create(
        cycle=1,
        requesting_role=AgentRole.FORGE,
        action_digest=action_digest,
        requested_authority="tool-execution",
        summary="Run network client.",
        tool_key="network-client",
        requires_tool=True,
        requires_human_boundary=False,
    )

    decision = decide_authority_request(
        request=request,
        contract=_contract(),
        jurisdiction_gate=_gate(),
    )

    assert decision.status is AuthorityDecisionStatus.DENIED
    assert decision.contract_note == "tool is not allowed by autonomy contract: network-client"


def test_decide_authority_request_denies_memory_write_when_contract_blocks_it() -> None:
    action_digest = DigestRecord.from_payload({"action": "write memory"})
    request = AuthorityRequest.create(
        cycle=1,
        requesting_role=AgentRole.MNEMOSYNE,
        action_digest=action_digest,
        requested_authority="memory-storage",
        summary="Write verified memory.",
        requires_memory_write=True,
        requires_human_boundary=False,
    )

    decision = decide_authority_request(
        request=request,
        contract=_contract(memory_writes_allowed=False),
        jurisdiction_gate=_gate(),
    )

    assert decision.status is AuthorityDecisionStatus.DENIED
    assert decision.contract_note == "memory writes are not allowed by autonomy contract"


def test_decide_authority_request_routes_human_boundary_review() -> None:
    action_digest = DigestRecord.from_payload({"action": "run tests"})
    request = AuthorityRequest.create(
        cycle=1,
        requesting_role=AgentRole.FORGE,
        action_digest=action_digest,
        requested_authority="tool-execution",
        summary="Run tests after human boundary review.",
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=True,
    )

    decision = decide_authority_request(
        request=request,
        contract=_contract(),
        jurisdiction_gate=_gate(),
    )

    assert decision.status is AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED
    assert decision.requires_human_review() is True
    assert decision.human_review_note == "human boundary review is required before action execution"


def test_authority_decision_ledger_filters_denied_and_human_review() -> None:
    request_digest = DigestRecord.from_payload({"request": "tool"})
    allowed = AuthorityDecision.create(
        cycle=1,
        request_digest=request_digest,
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Allowed.",
    )
    denied = AuthorityDecision.create(
        cycle=1,
        request_digest=request_digest,
        status=AuthorityDecisionStatus.DENIED,
        rationale="Denied.",
        contract_note="Denied by contract.",
    )
    human = AuthorityDecision.create(
        cycle=1,
        request_digest=request_digest,
        status=AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED,
        rationale="Human review.",
        human_review_note="Human review required.",
    )
    ledger = AuthorityDecisionLedger.create((allowed, denied, human))

    assert ledger.denied_decisions() == (denied,)
    assert ledger.human_review_decisions() == (human,)


def test_authority_decision_ledger_rejects_duplicate_decision_ids() -> None:
    request_digest = DigestRecord.from_payload({"request": "tool"})
    decision_id = CanonicalKey.from_text("same-decision", field_name="decision_id")
    first = AuthorityDecision.create(
        decision_id=decision_id,
        cycle=1,
        request_digest=request_digest,
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="First.",
    )
    second = AuthorityDecision.create(
        decision_id=decision_id,
        cycle=1,
        request_digest=request_digest,
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Second.",
    )

    with pytest.raises(FoundationError, match="duplicate authority decision id"):
        AuthorityDecisionLedger.create((first, second))


def test_authority_decision_digest_changes_when_status_changes() -> None:
    request_digest = DigestRecord.from_payload({"request": "tool"})
    allowed = AuthorityDecision.create(
        cycle=1,
        request_digest=request_digest,
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Allowed.",
    )
    denied = AuthorityDecision.create(
        cycle=1,
        request_digest=request_digest,
        status=AuthorityDecisionStatus.DENIED,
        rationale="Denied.",
        contract_note="Denied by contract.",
    )

    assert allowed.digest().value != denied.digest().value
