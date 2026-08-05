"""Bounded action records for IX-Sally proposal-to-authority flow."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus, AuthorityRequest
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_optional_text, require_text
from ix_sally.proposals import ProposalAction


class ActionStatus(StrEnum):
    """Status assigned to a bounded action as it moves through authority gates."""

    PROPOSED = "proposed"
    AUTHORITY_REQUESTED = "authority_requested"
    AUTHORIZED = "authorized"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    DENIED = "denied"
    EXECUTED = "executed"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class BoundedActionRecord:
    """A proposed action that cannot execute until authority and boundary checks pass."""

    action_id: CanonicalKey
    cycle: int
    proposed_by: AgentRole
    description: str
    requested_authority: CanonicalKey
    proposal_action_digest: DigestRecord
    status: ActionStatus = ActionStatus.PROPOSED
    tool_key: CanonicalKey | None = None
    requires_tool: bool = False
    requires_memory_write: bool = False
    requires_human_boundary: bool = True
    authority_decision_digest: DigestRecord | None = None
    execution_digest: DigestRecord | None = None
    boundary_note: str | None = None

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        proposed_by: AgentRole,
        description: str,
        requested_authority: str,
        proposal_action_digest: DigestRecord,
        status: ActionStatus = ActionStatus.PROPOSED,
        tool_key: str | None = None,
        requires_tool: bool = False,
        requires_memory_write: bool = False,
        requires_human_boundary: bool = True,
        authority_decision_digest: DigestRecord | None = None,
        execution_digest: DigestRecord | None = None,
        boundary_note: str | None = None,
        action_id: CanonicalKey | None = None,
    ) -> BoundedActionRecord:
        """Create a normalized bounded action record."""
        if cycle < 0:
            raise FoundationError("bounded action cycle must not be negative")

        proposal_action_digest.require_algorithm("sha256")
        if authority_decision_digest is not None:
            authority_decision_digest.require_algorithm("sha256")
        if execution_digest is not None:
            execution_digest.require_algorithm("sha256")

        normalized_description = require_text(description, field_name="description")
        normalized_authority = CanonicalKey.from_text(
            requested_authority,
            field_name="requested_authority",
        )
        normalized_tool = (
            CanonicalKey.from_text(tool_key, field_name="tool_key")
            if tool_key is not None
            else None
        )
        normalized_boundary_note = require_optional_text(
            boundary_note,
            field_name="boundary_note",
        )

        if requires_tool and normalized_tool is None:
            raise FoundationError("bounded tool actions require a tool key")

        if status in {ActionStatus.DENIED, ActionStatus.BLOCKED}:
            if normalized_boundary_note is None:
                raise FoundationError("denied or blocked bounded actions require a boundary note")

        if status is ActionStatus.AUTHORIZED and authority_decision_digest is None:
            raise FoundationError("authorized bounded actions require an authority decision digest")

        if status is ActionStatus.EXECUTED and execution_digest is None:
            raise FoundationError("executed bounded actions require an execution digest")

        return cls(
            action_id=action_id
            or CanonicalKey.from_text(
                f"{proposed_by.value}-{cycle}-{normalized_authority.value}"
                f"-{normalized_description}",
                field_name="action_id",
            ),
            cycle=cycle,
            proposed_by=proposed_by,
            description=normalized_description,
            requested_authority=normalized_authority,
            proposal_action_digest=proposal_action_digest,
            status=status,
            tool_key=normalized_tool,
            requires_tool=requires_tool,
            requires_memory_write=requires_memory_write,
            requires_human_boundary=requires_human_boundary,
            authority_decision_digest=authority_decision_digest,
            execution_digest=execution_digest,
            boundary_note=normalized_boundary_note,
        )

    @classmethod
    def from_proposal_action(
        cls,
        *,
        cycle: int,
        proposed_by: AgentRole,
        proposal_action: ProposalAction,
        tool_key: str | None = None,
    ) -> BoundedActionRecord:
        """Create a bounded action record from a Sally proposal action."""
        return cls.create(
            action_id=proposal_action.action_id,
            cycle=cycle,
            proposed_by=proposed_by,
            description=proposal_action.description,
            requested_authority=proposal_action.intended_authority.value,
            proposal_action_digest=proposal_action.digest(),
            tool_key=tool_key,
            requires_tool=proposal_action.requires_tool,
            requires_memory_write=proposal_action.requires_memory_write,
            requires_human_boundary=proposal_action.requires_human_boundary,
        )

    def to_authority_request(self) -> AuthorityRequest:
        """Convert this bounded action into an authority request."""
        return AuthorityRequest.create(
            cycle=self.cycle,
            requesting_role=self.proposed_by,
            action_digest=self.digest(),
            requested_authority=self.requested_authority.value,
            summary=self.description,
            tool_key=self.tool_key.value if self.tool_key is not None else None,
            requires_tool=self.requires_tool,
            requires_memory_write=self.requires_memory_write,
            requires_human_boundary=self.requires_human_boundary,
        )

    def with_authority_decision(self, decision: AuthorityDecision) -> BoundedActionRecord:
        """Return this action updated with the result of an authority decision."""
        if decision.cycle != self.cycle:
            raise FoundationError("authority decision must match bounded action cycle")

        if decision.status is AuthorityDecisionStatus.ALLOWED:
            status = ActionStatus.AUTHORIZED
            note = self.boundary_note
        elif decision.status is AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED:
            status = ActionStatus.HUMAN_REVIEW_REQUIRED
            note = decision.human_review_note
        else:
            status = ActionStatus.DENIED
            note = decision.contract_note

        return BoundedActionRecord.create(
            action_id=self.action_id,
            cycle=self.cycle,
            proposed_by=self.proposed_by,
            description=self.description,
            requested_authority=self.requested_authority.value,
            proposal_action_digest=self.proposal_action_digest,
            status=status,
            tool_key=self.tool_key.value if self.tool_key is not None else None,
            requires_tool=self.requires_tool,
            requires_memory_write=self.requires_memory_write,
            requires_human_boundary=self.requires_human_boundary,
            authority_decision_digest=decision.digest(),
            execution_digest=self.execution_digest,
            boundary_note=note,
        )

    def with_execution_digest(self, execution_digest: DigestRecord) -> BoundedActionRecord:
        """Return this action marked as executed with an execution receipt digest."""
        if self.status is not ActionStatus.AUTHORIZED:
            raise FoundationError("only authorized bounded actions may be marked executed")

        return BoundedActionRecord.create(
            action_id=self.action_id,
            cycle=self.cycle,
            proposed_by=self.proposed_by,
            description=self.description,
            requested_authority=self.requested_authority.value,
            proposal_action_digest=self.proposal_action_digest,
            status=ActionStatus.EXECUTED,
            tool_key=self.tool_key.value if self.tool_key is not None else None,
            requires_tool=self.requires_tool,
            requires_memory_write=self.requires_memory_write,
            requires_human_boundary=self.requires_human_boundary,
            authority_decision_digest=self.authority_decision_digest,
            execution_digest=execution_digest,
            boundary_note=self.boundary_note,
        )

    def with_blocking_result(
        self,
        *,
        execution_digest: DigestRecord,
        boundary_note: str,
    ) -> BoundedActionRecord:
        """Return this action marked as blocked by a Forge execution result."""
        if self.status is not ActionStatus.AUTHORIZED:
            raise FoundationError("only authorized bounded actions may receive blocking results")

        return BoundedActionRecord.create(
            action_id=self.action_id,
            cycle=self.cycle,
            proposed_by=self.proposed_by,
            description=self.description,
            requested_authority=self.requested_authority.value,
            proposal_action_digest=self.proposal_action_digest,
            status=ActionStatus.BLOCKED,
            tool_key=self.tool_key.value if self.tool_key is not None else None,
            requires_tool=self.requires_tool,
            requires_memory_write=self.requires_memory_write,
            requires_human_boundary=self.requires_human_boundary,
            authority_decision_digest=self.authority_decision_digest,
            execution_digest=execution_digest,
            boundary_note=boundary_note,
        )

    def allows_execution(self) -> bool:
        """Return whether this bounded action is authorized for execution."""
        return self.status is ActionStatus.AUTHORIZED

    def requires_human_review(self) -> bool:
        """Return whether this bounded action is waiting on human review."""
        return self.status is ActionStatus.HUMAN_REVIEW_REQUIRED

    def blocks_progress(self) -> bool:
        """Return whether this bounded action blocks autonomous continuation."""
        return self.status in {
            ActionStatus.HUMAN_REVIEW_REQUIRED,
            ActionStatus.DENIED,
            ActionStatus.BLOCKED,
        }

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible bounded action representation."""
        return {
            "action_id": self.action_id.value,
            "cycle": self.cycle,
            "proposed_by": self.proposed_by.value,
            "description": self.description,
            "requested_authority": self.requested_authority.value,
            "proposal_action_digest": {
                "algorithm": self.proposal_action_digest.algorithm,
                "value": self.proposal_action_digest.value,
            },
            "status": self.status.value,
            "tool_key": self.tool_key.value if self.tool_key is not None else None,
            "requires_tool": self.requires_tool,
            "requires_memory_write": self.requires_memory_write,
            "requires_human_boundary": self.requires_human_boundary,
            "authority_decision_digest": (
                {
                    "algorithm": self.authority_decision_digest.algorithm,
                    "value": self.authority_decision_digest.value,
                }
                if self.authority_decision_digest is not None
                else None
            ),
            "execution_digest": (
                {
                    "algorithm": self.execution_digest.algorithm,
                    "value": self.execution_digest.value,
                }
                if self.execution_digest is not None
                else None
            ),
            "boundary_note": self.boundary_note,
            "allows_execution": self.allows_execution(),
            "requires_human_review": self.requires_human_review(),
            "blocks_progress": self.blocks_progress(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this bounded action record."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class BoundedActionLedger:
    """Immutable ledger of bounded actions proposed during a chamber run."""

    actions: tuple[BoundedActionRecord, ...]

    @classmethod
    def create(cls, actions: Iterable[BoundedActionRecord]) -> BoundedActionLedger:
        """Create an action ledger and reject duplicate action identifiers."""
        normalized = tuple(actions)
        seen: set[str] = set()

        for action in normalized:
            if action.action_id.value in seen:
                raise FoundationError(f"duplicate bounded action id: {action.action_id.value}")
            seen.add(action.action_id.value)

        return cls(actions=normalized)

    def append(self, action: BoundedActionRecord) -> BoundedActionLedger:
        """Return a new ledger with an appended bounded action."""
        return BoundedActionLedger.create((*self.actions, action))

    def replace(self, action: BoundedActionRecord) -> BoundedActionLedger:
        """Return a new ledger with an existing action replaced by identifier."""
        replaced = False
        updated: list[BoundedActionRecord] = []

        for existing in self.actions:
            if existing.action_id == action.action_id:
                updated.append(action)
                replaced = True
            else:
                updated.append(existing)

        if not replaced:
            raise FoundationError(f"unknown bounded action id: {action.action_id.value}")

        return BoundedActionLedger.create(tuple(updated))

    def require_action(self, action_id: str) -> BoundedActionRecord:
        """Return an action by identifier or raise a construction error."""
        requested = CanonicalKey.from_text(action_id, field_name="action_id")
        for action in self.actions:
            if action.action_id == requested:
                return action
        raise FoundationError(f"unknown bounded action id: {requested.value}")

    def executable_actions(self) -> tuple[BoundedActionRecord, ...]:
        """Return bounded actions authorized for execution."""
        return tuple(action for action in self.actions if action.allows_execution())

    def proposed_actions(self) -> tuple[BoundedActionRecord, ...]:
        """Return bounded actions still waiting for authority decisions."""
        return tuple(action for action in self.actions if action.status is ActionStatus.PROPOSED)

    def executed_actions(self) -> tuple[BoundedActionRecord, ...]:
        """Return bounded actions marked executed by Forge results."""
        return tuple(action for action in self.actions if action.status is ActionStatus.EXECUTED)

    def human_review_actions(self) -> tuple[BoundedActionRecord, ...]:
        """Return bounded actions waiting on human review."""
        return tuple(action for action in self.actions if action.requires_human_review())

    def blocked_actions(self) -> tuple[BoundedActionRecord, ...]:
        """Return bounded actions that block autonomous continuation."""
        return tuple(action for action in self.actions if action.blocks_progress())

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible bounded action ledger representation."""
        action_payload: JsonArray = []
        for action in self.actions:
            action_payload.append(action.to_payload())

        return {
            "actions": action_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this bounded action ledger."""
        return DigestRecord.from_payload(self.to_payload())
