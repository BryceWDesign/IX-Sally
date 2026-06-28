"""IX-Sally proposal packets emitted by the builder/proposer role."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifact, AgentArtifactKind
from ix_sally.claims import ClaimRecord
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


@dataclass(frozen=True, slots=True)
class ProposalAction:
    """A bounded action proposed by IX-Sally before challenge, evidence, or approval."""

    action_id: CanonicalKey
    description: str
    intended_authority: CanonicalKey
    requires_tool: bool = False
    requires_memory_write: bool = False
    requires_human_boundary: bool = True

    @classmethod
    def create(
        cls,
        *,
        description: str,
        intended_authority: str,
        requires_tool: bool = False,
        requires_memory_write: bool = False,
        requires_human_boundary: bool = True,
        action_id: CanonicalKey | None = None,
    ) -> ProposalAction:
        """Create a normalized proposal action."""
        normalized_description = require_text(description, field_name="description")
        authority = CanonicalKey.from_text(intended_authority, field_name="intended_authority")

        return cls(
            action_id=action_id
            or CanonicalKey.from_text(
                f"{authority.value}-{normalized_description}",
                field_name="action_id",
            ),
            description=normalized_description,
            intended_authority=authority,
            requires_tool=requires_tool,
            requires_memory_write=requires_memory_write,
            requires_human_boundary=requires_human_boundary,
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible proposal-action representation."""
        return {
            "action_id": self.action_id.value,
            "description": self.description,
            "intended_authority": self.intended_authority.value,
            "requires_tool": self.requires_tool,
            "requires_memory_write": self.requires_memory_write,
            "requires_human_boundary": self.requires_human_boundary,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this proposal action."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class SallyProposalPacket:
    """A structured proposal from IX-Sally that does not self-approve truth or action."""

    proposal_id: CanonicalKey
    cycle: int
    goal_interpretation: str
    rationale: str
    proposed_actions: tuple[ProposalAction, ...]
    claims: tuple[ClaimRecord, ...] = field(default_factory=tuple)

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        goal_interpretation: str,
        rationale: str,
        proposed_actions: Iterable[ProposalAction],
        claims: Iterable[ClaimRecord] = (),
        proposal_id: CanonicalKey | None = None,
    ) -> SallyProposalPacket:
        """Create a normalized IX-Sally proposal packet."""
        if cycle < 0:
            raise FoundationError("proposal cycle must not be negative")

        normalized_goal = require_text(goal_interpretation, field_name="goal_interpretation")
        normalized_rationale = require_text(rationale, field_name="rationale")
        normalized_actions = tuple(proposed_actions)
        normalized_claims = tuple(claims)

        if not normalized_actions:
            raise FoundationError("proposal requires at least one bounded action")

        for claim in normalized_claims:
            if claim.author is not AgentRole.SALLY:
                raise FoundationError("Sally proposal claims must be authored by ix-sally")
            if claim.cycle != cycle:
                raise FoundationError("Sally proposal claims must match proposal cycle")

        return cls(
            proposal_id=proposal_id
            or CanonicalKey.from_text(
                f"ix-sally-{cycle}-{normalized_goal}",
                field_name="proposal_id",
            ),
            cycle=cycle,
            goal_interpretation=normalized_goal,
            rationale=normalized_rationale,
            proposed_actions=normalized_actions,
            claims=normalized_claims,
        )

    def requires_tool_execution(self) -> bool:
        """Return whether any proposed action asks for tool execution."""
        return any(action.requires_tool for action in self.proposed_actions)

    def requires_memory_write(self) -> bool:
        """Return whether any proposed action asks to write memory."""
        return any(action.requires_memory_write for action in self.proposed_actions)

    def to_artifact(self) -> AgentArtifact:
        """Convert this packet into a shared runtime artifact."""
        return AgentArtifact.create(
            cycle=self.cycle,
            role=AgentRole.SALLY,
            kind=AgentArtifactKind.PROPOSAL,
            summary=f"IX-Sally proposed {len(self.proposed_actions)} bounded action(s).",
            referenced_digests=tuple(claim.digest() for claim in self.claims),
            data=self.to_payload(),
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible proposal packet representation."""
        actions_payload: JsonArray = []
        for action in self.proposed_actions:
            actions_payload.append(action.to_payload())

        claims_payload: JsonArray = []
        for claim in self.claims:
            claims_payload.append(claim.to_payload())

        return {
            "proposal_id": self.proposal_id.value,
            "cycle": self.cycle,
            "goal_interpretation": self.goal_interpretation,
            "rationale": self.rationale,
            "proposed_actions": actions_payload,
            "claims": claims_payload,
            "requires_tool_execution": self.requires_tool_execution(),
            "requires_memory_write": self.requires_memory_write(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this proposal packet."""
        return DigestRecord.from_payload(self.to_payload())
