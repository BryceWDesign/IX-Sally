"""Jurisdiction gates for IX-Sally agent role authority."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_sally.agents import AgentRole, AgentRoleRegistry
from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError


class JurisdictionStatus(StrEnum):
    """Status for an authority decision inside the ninefold runtime."""

    ALLOWED = "allowed"
    DENIED = "denied"


@dataclass(frozen=True, slots=True)
class JurisdictionDecision:
    """Decision describing whether a role may exercise a requested authority."""

    role: AgentRole
    authority: CanonicalKey
    status: JurisdictionStatus
    reason: str

    @property
    def allowed(self) -> bool:
        """Return whether the requested authority is allowed."""
        return self.status is JurisdictionStatus.ALLOWED

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible jurisdiction decision."""
        return {
            "role": self.role.value,
            "authority": self.authority.value,
            "status": self.status.value,
            "reason": self.reason,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this jurisdiction decision."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class JurisdictionGate:
    """Gate enforcing non-overlapping authority between IX-Sally agent roles."""

    registry: AgentRoleRegistry

    def evaluate(self, *, role: AgentRole, authority: str) -> JurisdictionDecision:
        """Evaluate whether a role may exercise an authority."""
        definition = self.registry.require_role(role)
        requested = CanonicalKey.from_text(authority, field_name="authority")

        if definition.prohibits(requested.value):
            return JurisdictionDecision(
                role=role,
                authority=requested,
                status=JurisdictionStatus.DENIED,
                reason=(
                    f"role {role.value} is prohibited from authority {requested.value}"
                ),
            )

        return JurisdictionDecision(
            role=role,
            authority=requested,
            status=JurisdictionStatus.ALLOWED,
            reason=f"role {role.value} may exercise authority {requested.value}",
        )

    def require_allowed(self, *, role: AgentRole, authority: str) -> JurisdictionDecision:
        """Return an allowed decision or raise when a role exceeds jurisdiction."""
        decision = self.evaluate(role=role, authority=authority)
        if not decision.allowed:
            raise FoundationError(decision.reason)
        return decision
