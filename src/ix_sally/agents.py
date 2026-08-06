"""Ninefold agent role definitions for IX-Sally."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class AgentRole(StrEnum):
    """Canonical IX-Sally ninefold agent roles."""

    SALLY = "ix-sally"
    BUTCH = "ix-butch"
    VERITY = "ix-verity"
    ORACLE = "ix-oracle"
    FORGE = "ix-forge"
    MNEMOSYNE = "ix-mnemosyne"
    SENTINEL = "ix-sentinel"
    TRANSFER = "ix-transfer"
    CLERK = "ix-clerk"


@dataclass(frozen=True, slots=True)
class AgentRoleDefinition:
    """Definition of one IX-Sally agent role and its non-overlapping duty."""

    role: AgentRole
    title: str
    duty: str
    prohibited_authorities: tuple[CanonicalKey, ...]

    @classmethod
    def create(
        cls,
        *,
        role: AgentRole,
        title: str,
        duty: str,
        prohibited_authorities: Iterable[str] = (),
    ) -> AgentRoleDefinition:
        """Create a normalized role definition."""
        return cls(
            role=role,
            title=require_text(title, field_name="title"),
            duty=require_text(duty, field_name="duty"),
            prohibited_authorities=tuple(
                CanonicalKey.from_text(authority, field_name="prohibited_authority")
                for authority in prohibited_authorities
            ),
        )

    def prohibits(self, authority: str) -> bool:
        """Return whether this role is prohibited from exercising an authority."""
        requested = CanonicalKey.from_text(authority, field_name="authority")
        return requested in self.prohibited_authorities

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible role definition."""
        prohibited_payload: JsonArray = []
        for authority in self.prohibited_authorities:
            prohibited_payload.append(authority.value)

        return {
            "role": self.role.value,
            "title": self.title,
            "duty": self.duty,
            "prohibited_authorities": prohibited_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this role definition."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class AgentRoleRegistry:
    """Immutable registry of IX-Sally role definitions."""

    definitions: tuple[AgentRoleDefinition, ...]

    @classmethod
    def create(cls, definitions: Iterable[AgentRoleDefinition]) -> AgentRoleRegistry:
        """Create a registry and reject duplicate or incomplete role coverage."""
        normalized = tuple(definitions)
        seen: set[AgentRole] = set()
        for definition in normalized:
            if definition.role in seen:
                raise FoundationError(f"duplicate agent role definition: {definition.role.value}")
            seen.add(definition.role)

        return cls(definitions=normalized)

    def require_role(self, role: AgentRole) -> AgentRoleDefinition:
        """Return a role definition or raise a construction error."""
        for definition in self.definitions:
            if definition.role is role:
                return definition
        raise FoundationError(f"unknown agent role: {role.value}")

    def require_complete_ninefold(self) -> None:
        """Reject a registry that does not define all nine IX-Sally roles."""
        defined = {definition.role for definition in self.definitions}
        missing = [role.value for role in AgentRole if role not in defined]
        if missing:
            joined = ", ".join(missing)
            raise FoundationError(f"missing ninefold agent roles: {joined}")

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible registry representation."""
        return {
            "definitions": [definition.to_payload() for definition in self.definitions],
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this role registry."""
        return DigestRecord.from_payload(self.to_payload())


def default_agent_role_registry() -> AgentRoleRegistry:
    """Return IX-Sally's default ninefold role registry."""
    registry = AgentRoleRegistry.create(
        (
            AgentRoleDefinition.create(
                role=AgentRole.SALLY,
                title="Builder and proposer",
                duty="Creates proposals, plans, hypotheses, code intentions, and response drafts.",
                prohibited_authorities=(
                    "evidence-judgment",
                    "verified-memory-write",
                    "boundary-override",
                    "execution-approval",
                ),
            ),
            AgentRoleDefinition.create(
                role=AgentRole.BUTCH,
                title="Adversary and falsifier",
                duty=(
                    "Attacks assumptions, contradictions, weak plans, "
                    "unsupported claims, and drift."
                ),
                prohibited_authorities=(
                    "verified-memory-write",
                    "execution-approval",
                    "final-evidence-verdict",
                ),
            ),
            AgentRoleDefinition.create(
                role=AgentRole.VERITY,
                title="Evidence judge",
                duty=(
                    "Judges whether claims are supported, unsupported, "
                    "contradicted, blocked, or pending."
                ),
                prohibited_authorities=(
                    "tool-execution",
                    "memory-storage",
                    "proposal-authorship",
                ),
            ),
            AgentRoleDefinition.create(
                role=AgentRole.ORACLE,
                title="Prediction and world-model forecaster",
                duty="Records expected outcomes before action so reality-delta can be measured.",
                prohibited_authorities=(
                    "tool-execution",
                    "verified-memory-write",
                    "final-evidence-verdict",
                ),
            ),
            AgentRoleDefinition.create(
                role=AgentRole.FORGE,
                title="Executor and sandbox tester",
                duty=(
                    "Runs allowed tool actions, command checks, and executable tests inside scope."
                ),
                prohibited_authorities=(
                    "final-evidence-verdict",
                    "verified-memory-write",
                    "boundary-override",
                ),
            ),
            AgentRoleDefinition.create(
                role=AgentRole.MNEMOSYNE,
                title="Memory law and learning keeper",
                duty=(
                    "Classifies memory candidates as pending, verified, stale, "
                    "contradicted, or quarantined."
                ),
                prohibited_authorities=(
                    "tool-execution",
                    "proposal-authorship",
                    "boundary-override",
                ),
            ),
            AgentRoleDefinition.create(
                role=AgentRole.SENTINEL,
                title="Safety and boundary guard",
                duty=(
                    "Detects manipulation pressure, unsafe escalation, "
                    "unauthorized scope, and drift."
                ),
                prohibited_authorities=(
                    "proposal-authorship",
                    "verified-memory-write",
                    "final-evidence-verdict",
                ),
            ),
            AgentRoleDefinition.create(
                role=AgentRole.TRANSFER,
                title="Generalization tester",
                duty=(
                    "Tests whether learned patterns transfer beyond the "
                    "originating task or context."
                ),
                prohibited_authorities=(
                    "tool-execution",
                    "verified-memory-write",
                    "boundary-override",
                ),
            ),
            AgentRoleDefinition.create(
                role=AgentRole.CLERK,
                title="Recorder and receipt officer",
                duty="Records transcripts, decisions, receipts, ledgers, and run dossiers.",
                prohibited_authorities=(
                    "proposal-authorship",
                    "tool-execution",
                    "final-evidence-verdict",
                    "verified-memory-write",
                ),
            ),
        )
    )
    registry.require_complete_ninefold()
    return registry
