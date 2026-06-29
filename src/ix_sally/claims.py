"""Claim records for IX-Sally evidence-grounded reasoning."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from ix_sally.agents import AgentRole
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class ClaimStatus(StrEnum):
    """Status assigned to a claim during evidence review."""

    PROPOSED = "proposed"
    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"


@dataclass(frozen=True, slots=True)
class ClaimRecord:
    """One agent-authored claim that must be grounded by evidence."""

    claim_id: CanonicalKey
    cycle: int
    author: AgentRole
    statement: str
    status: ClaimStatus = ClaimStatus.PROPOSED

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        author: AgentRole,
        statement: str,
        status: ClaimStatus = ClaimStatus.PROPOSED,
        claim_id: CanonicalKey | None = None,
    ) -> ClaimRecord:
        """Create a normalized claim record."""
        if cycle < 0:
            raise FoundationError("claim cycle must not be negative")

        normalized_statement = require_text(statement, field_name="statement")

        return cls(
            claim_id=claim_id
            or CanonicalKey.from_text(
                f"{author.value}-{cycle}-{normalized_statement}",
                field_name="claim_id",
            ),
            cycle=cycle,
            author=author,
            statement=normalized_statement,
            status=status,
        )

    def with_status(self, status: ClaimStatus) -> ClaimRecord:
        """Return this claim with an updated review status."""
        return ClaimRecord.create(
            claim_id=self.claim_id,
            cycle=self.cycle,
            author=self.author,
            statement=self.statement,
            status=status,
        )

    def requires_human_review(self) -> bool:
        """Return whether this claim status requires human review."""
        return self.status in {
            ClaimStatus.PARTIAL,
            ClaimStatus.UNSUPPORTED,
            ClaimStatus.CONTRADICTED,
        }

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible claim representation."""
        return {
            "claim_id": self.claim_id.value,
            "cycle": self.cycle,
            "author": self.author.value,
            "statement": self.statement,
            "status": self.status.value,
            "requires_human_review": self.requires_human_review(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this claim."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ClaimLedger:
    """Immutable ledger of claims made during a chamber run."""

    claims: tuple[ClaimRecord, ...]

    @classmethod
    def create(cls, claims: Iterable[ClaimRecord]) -> ClaimLedger:
        """Create a claim ledger and reject duplicate claim identifiers."""
        normalized = tuple(claims)
        seen: set[str] = set()

        for claim in normalized:
            if claim.claim_id.value in seen:
                raise FoundationError(f"duplicate claim id: {claim.claim_id.value}")
            seen.add(claim.claim_id.value)

        return cls(claims=normalized)

    def append(self, claim: ClaimRecord) -> ClaimLedger:
        """Return a new ledger with an appended claim."""
        return ClaimLedger.create((*self.claims, claim))

    def require_claim(self, claim_id: str) -> ClaimRecord:
        """Return a claim by identifier or raise a construction error."""
        requested = CanonicalKey.from_text(claim_id, field_name="claim_id")
        for claim in self.claims:
            if claim.claim_id == requested:
                return claim
        raise FoundationError(f"unknown claim id: {requested.value}")

    def supported_claims(self) -> tuple[ClaimRecord, ...]:
        """Return claims marked supported."""
        return tuple(claim for claim in self.claims if claim.status is ClaimStatus.SUPPORTED)

    def human_review_claims(self) -> tuple[ClaimRecord, ...]:
        """Return claims requiring human review."""
        return tuple(claim for claim in self.claims if claim.requires_human_review())

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible claim ledger representation."""
        claim_payload: JsonArray = []
        for claim in self.claims:
            claim_payload.append(claim.to_payload())

        return {
            "claims": claim_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this claim ledger."""
        return DigestRecord.from_payload(self.to_payload())
