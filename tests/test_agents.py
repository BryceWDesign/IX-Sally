

from __future__ import annotations

import pytest
from ix_sally.agents import (
    AgentRole,
    AgentRoleDefinition,
    AgentRoleRegistry,
    default_agent_role_registry,
)
from ix_sally.foundation import FoundationError


def test_agent_role_definition_normalizes_fields() -> None:
    definition = AgentRoleDefinition.create(
        role=AgentRole.SALLY,
        title="  Builder and proposer  ",
        duty="  Creates proposals. ",
        prohibited_authorities=(" Evidence Judgment ", "Verified Memory Write"),
    )

    assert definition.title == "Builder and proposer"
    assert definition.duty == "Creates proposals."
    assert [authority.value for authority in definition.prohibited_authorities] == [
        "evidence-judgment",
        "verified-memory-write",
    ]


def test_agent_role_definition_checks_prohibited_authority() -> None:
    definition = AgentRoleDefinition.create(
        role=AgentRole.VERITY,
        title="Evidence judge",
        duty="Judges evidence.",
        prohibited_authorities=("tool-execution",),
    )

    assert definition.prohibits("Tool Execution") is True
    assert definition.prohibits("evidence-judgment") is False


def test_agent_role_registry_rejects_duplicate_roles() -> None:
    first = AgentRoleDefinition.create(
        role=AgentRole.SALLY,
        title="Builder",
        duty="Creates proposals.",
    )
    second = AgentRoleDefinition.create(
        role=AgentRole.SALLY,
        title="Duplicate builder",
        duty="Duplicates proposals.",
    )

    with pytest.raises(FoundationError, match="duplicate agent role definition"):
        AgentRoleRegistry.create((first, second))


def test_agent_role_registry_requires_known_role() -> None:
    definition = AgentRoleDefinition.create(
        role=AgentRole.BUTCH,
        title="Adversary",
        duty="Challenges claims.",
    )
    registry = AgentRoleRegistry.create((definition,))

    assert registry.require_role(AgentRole.BUTCH) == definition

    with pytest.raises(FoundationError, match="unknown agent role"):
        registry.require_role(AgentRole.VERITY)


def test_agent_role_registry_requires_complete_ninefold() -> None:
    registry = AgentRoleRegistry.create(
        (
            AgentRoleDefinition.create(
                role=AgentRole.SALLY,
                title="Builder",
                duty="Creates proposals.",
            ),
        )
    )

    with pytest.raises(FoundationError, match="missing ninefold agent roles"):
        registry.require_complete_ninefold()


def test_default_registry_defines_all_nine_roles() -> None:
    registry = default_agent_role_registry()
    roles = {definition.role for definition in registry.definitions}

    assert roles == set(AgentRole)
    assert len(registry.definitions) == 9


def test_default_registry_keeps_truth_authority_out_of_sally() -> None:
    registry = default_agent_role_registry()
    sally = registry.require_role(AgentRole.SALLY)

    assert sally.prohibits("final-evidence-verdict") is False
    assert sally.prohibits("evidence-judgment") is True
    assert sally.prohibits("verified-memory-write") is True


def test_registry_digest_changes_when_role_duty_changes() -> None:
    first = AgentRoleRegistry.create(
        (
            AgentRoleDefinition.create(
                role=AgentRole.SALLY,
                title="Builder",
                duty="Creates proposals.",
            ),
        )
    )
    second = AgentRoleRegistry.create(
        (
            AgentRoleDefinition.create(
                role=AgentRole.SALLY,
                title="Builder",
                duty="Creates only bounded proposals.",
            ),
        )
    )

    assert first.digest().value != second.digest().value
