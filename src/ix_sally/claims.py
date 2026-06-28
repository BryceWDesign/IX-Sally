"""Claim records for IX-Sally evidence-bound runtime behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterable

from ix_sally.agents import AgentRole
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class ClaimStatus(StrEnum):
    """Support status for a claim inside an IX-Sally chamber run."""

    PROPOSED = "proposed"
    PENDING_EVIDENCE = "pending_evidence"
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ClaimRecord:
    """A statement made inside the runtime that must not self-certify as truth."""

    claim_id: CanonicalKey
    cycle: int
    author: AgentRole
    statement: str
    status: ClaimStatus = ClaimStatus.PROPOSED
    support_digests: tuple[DigestRecord, ...] = field(default_factory=tuple)

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        author: AgentRole,
        statement: str,
        status: ClaimStatus = ClaimStatus.PROPOSED,
        support_digests: Iterable[DigestRecord] = (),
        claim_id: CanonicalKey | None = None,
    ) -> ClaimRecord:
        """Create a normalized claim record."""
        if cycle < 0:
            raise FoundationError("claim cycle must not be negative")

        normalized_statement = require_text(statement, field_name="statement")
        normalized_support = tuple(support_digests)
        for support_digest in normalized_support:
            support_digest.require_algorithm("sha256")

        if status is ClaimStatus.SUPPORTED and not normalized_support:
            raise FoundationError("supported claims require at least one support digest")

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
            support_digests=normalized_support,
        )

    def with_status(
        self,
        status: ClaimStatus,
        *,
        support_digests: Iterable[DigestRecord] | None = None,
    ) -> ClaimRecord:
        """Return this claim with a new support status."""
        return ClaimRecord.create(
            cycle=self.cycle,
            author=self.author,
            statement=self.statement,
            status=status,
            support_digests=self.support_digests if support_digests is None else support_digests,
            claim_id=self.claim_id,
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible claim representation."""
        support_payload: JsonArray = []
        for support_digest in self.support_digests:
            support_payload.append(
                {
                    "algorithm": support_digest.algorithm,
                    "value": support_digest.value,
                }
            )

        return {
            "claim_id": self.claim_id.value,
            "cycle": self.cycle,
            "author": self.author.value,
            "statement": self.statement,
            "status": self.status.value,
            "support_digests": support_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this claim record."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ClaimLedger:
    """Immutable ledger of claims created during a chamber run."""

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

    def by_status(self, status: ClaimStatus) -> tuple[ClaimRecord, ...]:
        """Return all claims matching the requested status."""
        return tuple(claim for claim in self.claims if claim.status is status)

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
