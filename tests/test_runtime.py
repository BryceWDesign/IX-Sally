

from __future__ import annotations

import pytest
from ix_sally.agents import AgentRole, AgentRoleDefinition, AgentRoleRegistry
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.events import RuntimeEventType
from ix_sally.foundation import FoundationError
from ix_sally.jurisdiction import JurisdictionStatus
from ix_sally.runtime import NinefoldRuntimeKit


def _contract(*, goal: str = "Run bounded ninefold chamber.") -> AutonomyContract:
    return AutonomyContract.create(
        goal=goal,
        mode=AutonomyMode.OBSERVE,
        max_cycles=2,
        doctrine_keys=(
            "output-is-not-evidence",
            "memory-is-not-truth",
            "human-authority-remains-at-the-boundary",
        ),
    )


def test_runtime_kit_composes_chamber_registry_and_jurisdiction_gate() -> None:
    kit = NinefoldRuntimeKit.create(contract=_contract())

    assert kit.chamber.contract.goal == "Run bounded ninefold chamber."
    assert len(kit.role_registry.definitions) == 9
    assert kit.role_definition(AgentRole.SALLY).role is AgentRole.SALLY

    denied = kit.evaluate_authority(role=AgentRole.SALLY, authority="evidence judgment")
    allowed = kit.evaluate_authority(role=AgentRole.FORGE, authority="tool execution")

    assert denied.status is JurisdictionStatus.DENIED
    assert allowed.status is JurisdictionStatus.ALLOWED


def test_runtime_kit_rejects_incomplete_role_registry() -> None:
    incomplete_registry = AgentRoleRegistry.create(
        (
            AgentRoleDefinition.create(
                role=AgentRole.SALLY,
                title="Builder",
                duty="Creates proposals.",
            ),
        )
    )

    with pytest.raises(FoundationError, match="missing ninefold agent roles"):
        NinefoldRuntimeKit.create(
            contract=_contract(),
            role_registry=incomplete_registry,
        )


def test_runtime_kit_rejects_contract_with_missing_doctrine_binding() -> None:
    contract = AutonomyContract.create(
        goal="Run bounded chamber.",
        mode=AutonomyMode.OBSERVE,
        max_cycles=1,
        doctrine_keys=("missing-doctrine-rule",),
    )

    with pytest.raises(FoundationError, match="unknown doctrine rule"):
        NinefoldRuntimeKit.create(contract=contract)


def test_runtime_kit_require_authority_returns_allowed_decision() -> None:
    kit = NinefoldRuntimeKit.create(contract=_contract())

    decision = kit.require_authority(role=AgentRole.FORGE, authority="tool execution")

    assert decision.allowed is True
    assert decision.role is AgentRole.FORGE


def test_runtime_kit_require_authority_rejects_forbidden_decision() -> None:
    kit = NinefoldRuntimeKit.create(contract=_contract())

    with pytest.raises(
        FoundationError,
        match="role ix-sally is prohibited from authority evidence-judgment",
    ):
        kit.require_authority(role=AgentRole.SALLY, authority="evidence judgment")


def test_runtime_kit_can_assert_expected_denial() -> None:
    kit = NinefoldRuntimeKit.create(contract=_contract())

    kit.deny_if_authority_allowed(role=AgentRole.SALLY, authority="evidence judgment")

    with pytest.raises(FoundationError, match="authority unexpectedly allowed"):
        kit.deny_if_authority_allowed(role=AgentRole.FORGE, authority="tool execution")


def test_runtime_kit_opening_event_records_integrated_digests() -> None:
    kit = NinefoldRuntimeKit.create(contract=_contract())
    event = kit.opening_event(sequence=3)

    assert event.sequence == 3
    assert event.cycle == 0
    assert event.event_type is RuntimeEventType.CHAMBER_OPENED
    assert event.summary == (
        "IX-Sally chamber opened with doctrine, ninefold roles, and jurisdiction gates."
    )
    assert event.payload["contract_digest"] == kit.chamber.contract.digest().value
    assert event.payload["doctrine_digest"] == kit.chamber.doctrine_catalog.digest().value
    assert event.payload["chamber_digest"] == kit.chamber.digest().value
    assert event.payload["role_registry_digest"] == kit.role_registry.digest().value
    assert event.payload["mode"] == "observe"
    assert event.payload["max_cycles"] == 2
    assert event.payload["role_count"] == 9
    assert event.payload["sandbox_required"] is True


def test_runtime_kit_payload_is_stable() -> None:
    kit = NinefoldRuntimeKit.create(
        contract=_contract(),
        observer_label="reviewer",
        sandbox_required=True,
    )

    payload = kit.to_payload()

    assert payload["contract_digest"] == kit.chamber.contract.digest().value
    assert payload["doctrine_digest"] == kit.chamber.doctrine_catalog.digest().value
    assert payload["chamber_digest"] == kit.chamber.digest().value
    assert payload["role_registry_digest"] == kit.role_registry.digest().value
    assert payload["observer_label"] == "reviewer"
    assert payload["role_count"] == 9
    assert payload["sandbox_required"] is True
    assert payload["external_messaging_allowed"] is False


def test_runtime_kit_digest_changes_when_contract_changes() -> None:
    first = NinefoldRuntimeKit.create(contract=_contract(goal="First goal."))
    second = NinefoldRuntimeKit.create(contract=_contract(goal="Second goal."))

    assert first.digest().value != second.digest().value
