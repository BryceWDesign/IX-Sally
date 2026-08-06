"""Authority request records for IX-Sally action gating."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.agents import AgentRole
from ix_sally.contracts import AutonomyContract
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_optional_text, require_text
from ix_sally.jurisdiction import JurisdictionDecision, JurisdictionGate


class AuthorityDecisionStatus(StrEnum):
    """Status assigned to an IX-Sally authority request."""

    ALLOWED = "allowed"
    DENIED = "denied"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


@dataclass(frozen=True, slots=True)
class AuthorityRequest:
    """A request to exercise authority before action, tool use, or memory write."""

    request_id: CanonicalKey
    cycle: int
    requesting_role: AgentRole
    action_digest: DigestRecord
    requested_authority: CanonicalKey
    summary: str
    tool_key: CanonicalKey | None = None
    requires_tool: bool = False
    requires_memory_write: bool = False
    requires_human_boundary: bool = True

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        requesting_role: AgentRole,
        action_digest: DigestRecord,
        requested_authority: str,
        summary: str,
        tool_key: str | None = None,
        requires_tool: bool = False,
        requires_memory_write: bool = False,
        requires_human_boundary: bool = True,
        request_id: CanonicalKey | None = None,
    ) -> AuthorityRequest:
        """Create a normalized authority request."""
        if cycle < 0:
            raise FoundationError("authority request cycle must not be negative")

        action_digest.require_algorithm("sha256")
        normalized_authority = CanonicalKey.from_text(
            requested_authority,
            field_name="requested_authority",
        )
        normalized_summary = require_text(summary, field_name="summary")
        normalized_tool_key = (
            CanonicalKey.from_text(tool_key, field_name="tool_key")
            if tool_key is not None
            else None
        )

        if requires_tool and normalized_tool_key is None:
            raise FoundationError("tool authority requests require a tool key")

        return cls(
            request_id=request_id
            or CanonicalKey.from_text(
                f"{requesting_role.value}-{cycle}-{normalized_authority.value}"
                f"-{normalized_summary}",
                field_name="request_id",
            ),
            cycle=cycle,
            requesting_role=requesting_role,
            action_digest=action_digest,
            requested_authority=normalized_authority,
            summary=normalized_summary,
            tool_key=normalized_tool_key,
            requires_tool=requires_tool,
            requires_memory_write=requires_memory_write,
            requires_human_boundary=requires_human_boundary,
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible authority request representation."""
        return {
            "request_id": self.request_id.value,
            "cycle": self.cycle,
            "requesting_role": self.requesting_role.value,
            "action_digest": {
                "algorithm": self.action_digest.algorithm,
                "value": self.action_digest.value,
            },
            "requested_authority": self.requested_authority.value,
            "summary": self.summary,
            "tool_key": self.tool_key.value if self.tool_key is not None else None,
            "requires_tool": self.requires_tool,
            "requires_memory_write": self.requires_memory_write,
            "requires_human_boundary": self.requires_human_boundary,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this authority request."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class AuthorityDecision:
    """Decision over a requested authority after contract and jurisdiction checks."""

    decision_id: CanonicalKey
    cycle: int
    request_digest: DigestRecord
    status: AuthorityDecisionStatus
    rationale: str
    jurisdiction_decision: JurisdictionDecision | None = None
    contract_note: str | None = None
    human_review_note: str | None = None

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        request_digest: DigestRecord,
        status: AuthorityDecisionStatus,
        rationale: str,
        jurisdiction_decision: JurisdictionDecision | None = None,
        contract_note: str | None = None,
        human_review_note: str | None = None,
        decision_id: CanonicalKey | None = None,
    ) -> AuthorityDecision:
        """Create a normalized authority decision."""
        if cycle < 0:
            raise FoundationError("authority decision cycle must not be negative")

        request_digest.require_algorithm("sha256")
        normalized_rationale = require_text(rationale, field_name="rationale")
        normalized_contract_note = require_optional_text(
            contract_note,
            field_name="contract_note",
        )
        normalized_human_note = require_optional_text(
            human_review_note,
            field_name="human_review_note",
        )

        if status is AuthorityDecisionStatus.DENIED and normalized_contract_note is None:
            raise FoundationError("denied authority decisions require a contract note")

        if (
            status is AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED
            and normalized_human_note is None
        ):
            raise FoundationError("human-review authority decisions require a human note")

        return cls(
            decision_id=decision_id
            or CanonicalKey.from_text(
                f"authority-decision-{cycle}-{status.value}-{normalized_rationale}",
                field_name="decision_id",
            ),
            cycle=cycle,
            request_digest=request_digest,
            status=status,
            rationale=normalized_rationale,
            jurisdiction_decision=jurisdiction_decision,
            contract_note=normalized_contract_note,
            human_review_note=normalized_human_note,
        )

    def allows_action(self) -> bool:
        """Return whether this decision allows autonomous continuation."""
        return self.status is AuthorityDecisionStatus.ALLOWED

    def requires_human_review(self) -> bool:
        """Return whether this decision requires human review before continuation."""
        return self.status is AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED

    def denies_action(self) -> bool:
        """Return whether this decision denies the requested authority."""
        return self.status is AuthorityDecisionStatus.DENIED

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible authority decision representation."""
        return {
            "decision_id": self.decision_id.value,
            "cycle": self.cycle,
            "request_digest": {
                "algorithm": self.request_digest.algorithm,
                "value": self.request_digest.value,
            },
            "status": self.status.value,
            "rationale": self.rationale,
            "jurisdiction_decision": (
                self.jurisdiction_decision.to_payload()
                if self.jurisdiction_decision is not None
                else None
            ),
            "contract_note": self.contract_note,
            "human_review_note": self.human_review_note,
            "allows_action": self.allows_action(),
            "requires_human_review": self.requires_human_review(),
            "denies_action": self.denies_action(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this authority decision."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class AuthorityDecisionLedger:
    """Immutable ledger of authority decisions for a chamber run."""

    decisions: tuple[AuthorityDecision, ...]

    @classmethod
    def create(cls, decisions: Iterable[AuthorityDecision]) -> AuthorityDecisionLedger:
        """Create a decision ledger and reject duplicate decision identifiers."""
        normalized = tuple(decisions)
        seen: set[str] = set()

        for decision in normalized:
            if decision.decision_id.value in seen:
                raise FoundationError(
                    f"duplicate authority decision id: {decision.decision_id.value}"
                )
            seen.add(decision.decision_id.value)

        return cls(decisions=normalized)

    def append(self, decision: AuthorityDecision) -> AuthorityDecisionLedger:
        """Return a new ledger with an appended authority decision."""
        return AuthorityDecisionLedger.create((*self.decisions, decision))

    def denied_decisions(self) -> tuple[AuthorityDecision, ...]:
        """Return decisions denying requested authority."""
        return tuple(decision for decision in self.decisions if decision.denies_action())

    def human_review_decisions(self) -> tuple[AuthorityDecision, ...]:
        """Return decisions requiring human review."""
        return tuple(decision for decision in self.decisions if decision.requires_human_review())

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible decision ledger representation."""
        decision_payload: JsonArray = []
        for decision in self.decisions:
            decision_payload.append(decision.to_payload())

        return {
            "decisions": decision_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this authority decision ledger."""
        return DigestRecord.from_payload(self.to_payload())


def decide_authority_request(
    *,
    request: AuthorityRequest,
    contract: AutonomyContract,
    jurisdiction_gate: JurisdictionGate,
) -> AuthorityDecision:
    """Evaluate a request against contract scope and role jurisdiction."""
    jurisdiction = jurisdiction_gate.evaluate(
        role=request.requesting_role,
        authority=request.requested_authority.value,
    )

    if not jurisdiction.allowed:
        return AuthorityDecision.create(
            cycle=request.cycle,
            request_digest=request.digest(),
            status=AuthorityDecisionStatus.DENIED,
            rationale="Jurisdiction gate denied the requested authority.",
            jurisdiction_decision=jurisdiction,
            contract_note=jurisdiction.reason,
        )

    if request.requires_tool:
        if request.tool_key is None:
            raise FoundationError("tool authority requests require a tool key")
        try:
            contract.require_tool_allowed(request.tool_key.value)
        except FoundationError as error:
            return AuthorityDecision.create(
                cycle=request.cycle,
                request_digest=request.digest(),
                status=AuthorityDecisionStatus.DENIED,
                rationale="Autonomy contract denied the requested tool.",
                jurisdiction_decision=jurisdiction,
                contract_note=str(error),
            )

    if request.requires_memory_write and not contract.memory_writes_allowed:
        return AuthorityDecision.create(
            cycle=request.cycle,
            request_digest=request.digest(),
            status=AuthorityDecisionStatus.DENIED,
            rationale="Autonomy contract denied memory write authority.",
            jurisdiction_decision=jurisdiction,
            contract_note="memory writes are not allowed by autonomy contract",
        )

    if request.requires_human_boundary:
        return AuthorityDecision.create(
            cycle=request.cycle,
            request_digest=request.digest(),
            status=AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED,
            rationale=(
                "Requested action is inside role jurisdiction but requires human boundary review."
            ),
            jurisdiction_decision=jurisdiction,
            human_review_note="human boundary review is required before action execution",
        )

    return AuthorityDecision.create(
        cycle=request.cycle,
        request_digest=request.digest(),
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Requested authority is allowed by jurisdiction and autonomy contract.",
        jurisdiction_decision=jurisdiction,
    )
