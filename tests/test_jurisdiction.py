from __future__ import annotations

import pytest

from ix_sally.agents import AgentRole, default_agent_role_registry
from ix_sally.foundation import FoundationError
from ix_sally.jurisdiction import JurisdictionGate, JurisdictionStatus


def test_jurisdiction_gate_allows_authority_not_prohibited_for_role() -> None:
    gate = JurisdictionGate(default_agent_role_registry())

    decision = gate.evaluate(role=AgentRole.FORGE, authority="tool execution")

    assert decision.allowed is True
    assert decision.status is JurisdictionStatus.ALLOWED
    assert decision.authority.value == "tool-execution"
    assert decision.reason == "role ix-forge may exercise authority tool-execution"


def test_jurisdiction_gate_denies_prohibited_role_authority() -> None:
    gate = JurisdictionGate(default_agent_role_registry())

    decision = gate.evaluate(role=AgentRole.SALLY, authority="Evidence Judgment")

    assert decision.allowed is False
    assert decision.status is JurisdictionStatus.DENIED
    assert decision.authority.value == "evidence-judgment"
    assert decision.reason == "role ix-sally is prohibited from authority evidence-judgment"


def test_jurisdiction_gate_require_allowed_returns_allowed_decision() -> None:
    gate = JurisdictionGate(default_agent_role_registry())

    decision = gate.require_allowed(role=AgentRole.VERITY, authority="evidence-judgment")

    assert decision.allowed is True
    assert decision.role is AgentRole.VERITY


def test_jurisdiction_gate_require_allowed_rejects_boundary_violation() -> None:
    gate = JurisdictionGate(default_agent_role_registry())

    with pytest.raises(
        FoundationError,
        match="role ix-forge is prohibited from authority final-evidence-verdict",
    ):
        gate.require_allowed(role=AgentRole.FORGE, authority="final evidence verdict")


def test_jurisdiction_decision_payload_is_stable() -> None:
    gate = JurisdictionGate(default_agent_role_registry())

    decision = gate.evaluate(role=AgentRole.MNEMOSYNE, authority="memory storage")

    assert decision.to_payload() == {
        "role": "ix-mnemosyne",
        "authority": "memory-storage",
        "status": "allowed",
        "reason": "role ix-mnemosyne may exercise authority memory-storage",
    }


def test_jurisdiction_decision_digest_changes_when_status_changes() -> None:
    gate = JurisdictionGate(default_agent_role_registry())

    allowed = gate.evaluate(role=AgentRole.VERITY, authority="evidence-judgment")
    denied = gate.evaluate(role=AgentRole.VERITY, authority="tool-execution")

    assert allowed.digest().value != denied.digest().value
