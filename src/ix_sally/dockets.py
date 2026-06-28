"""IX-Clerk docket packets for receipt-grade run records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifact, AgentArtifactKind
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_optional_text, require_text


class DocketEntryKind(StrEnum):
    """Kinds of entries IX-Clerk may record in a chamber docket."""

    OBSERVATION = "observation"
    DECISION = "decision"
    RECEIPT_REFERENCE = "receipt_reference"
    BLOCKER = "blocker"
    HUMAN_BOUNDARY = "human_boundary"


@dataclass(frozen=True, slots=True)
class ClerkDocketEntry:
    """A single IX-Clerk docket entry that records what happened without judging truth."""

    entry_id: CanonicalKey
    cycle: int
    kind: DocketEntryKind
    summary: str
    actor: AgentRole | None = None
    reference_digest: DigestRecord | None = None
    requires_human_review: bool = False
    note: str | None = None

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        kind: DocketEntryKind,
        summary: str,
        actor: AgentRole | None = None,
        reference_digest: DigestRecord | None = None,
        requires_human_review: bool = False,
        note: str | None = None,
        entry_id: CanonicalKey | None = None,
    ) -> ClerkDocketEntry:
        """Create a normalized IX-Clerk docket entry."""
        if cycle < 0:
            raise FoundationError("docket entry cycle must not be negative")

        if reference_digest is not None:
            reference_digest.require_algorithm("sha256")

        normalized_summary = require_text(summary, field_name="summary")
        normalized_note = require_optional_text(note, field_name="note")

        if kind is DocketEntryKind.RECEIPT_REFERENCE and reference_digest is None:
            raise FoundationError("receipt-reference docket entries require a digest")

        if kind is DocketEntryKind.HUMAN_BOUNDARY and not requires_human_review:
            raise FoundationError("human-boundary docket entries require human review")

        if kind is DocketEntryKind.BLOCKER and normalized_note is None:
            raise FoundationError("blocker docket entries require a note")

        return cls(
            entry_id=entry_id
            or CanonicalKey.from_text(
                f"ix-clerk-{cycle}-{kind.value}-{normalized_summary}",
                field_name="entry_id",
            ),
            cycle=cycle,
            kind=kind,
            summary=normalized_summary,
            actor=actor,
            reference_digest=reference_digest,
            requires_human_review=requires_human_review,
            note=normalized_note,
        )

    def blocks_progress(self) -> bool:
        """Return whether this entry records a blocker or required human review."""
        return self.kind is DocketEntryKind.BLOCKER or self.requires_human_review

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible docket entry representation."""
        return {
            "entry_id": self.entry_id.value,
            "cycle": self.cycle,
            "kind": self.kind.value,
            "summary": self.summary,
            "actor": self.actor.value if self.actor is not None else None,
            "reference_digest": (
                {
                    "algorithm": self.reference_digest.algorithm,
                    "value": self.reference_digest.value,
                }
                if self.reference_digest is not None
                else None
            ),
            "requires_human_review": self.requires_human_review,
            "note": self.note,
            "blocks_progress": self.blocks_progress(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this docket entry."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ClerkDocketPacket:
    """Structured IX-Clerk docket packet for a chamber cycle."""

    packet_id: CanonicalKey
    cycle: int
    docket_summary: str
    entries: tuple[ClerkDocketEntry, ...]

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        docket_summary: str,
        entries: Iterable[ClerkDocketEntry],
        packet_id: CanonicalKey | None = None,
    ) -> ClerkDocketPacket:
        """Create a normalized IX-Clerk docket packet."""
        if cycle < 0:
            raise FoundationError("docket packet cycle must not be negative")

        normalized_summary = require_text(docket_summary, field_name="docket_summary")
        normalized_entries = tuple(entries)

        if not normalized_entries:
            raise FoundationError("docket packet requires at least one entry")

        for entry in normalized_entries:
            if entry.cycle != cycle:
                raise FoundationError("docket entries must match packet cycle")

        return cls(
            packet_id=packet_id
            or CanonicalKey.from_text(
                f"ix-clerk-{cycle}-{normalized_summary}",
                field_name="packet_id",
            ),
            cycle=cycle,
            docket_summary=normalized_summary,
            entries=normalized_entries,
        )

    def human_review_count(self) -> int:
        """Return the number of entries requiring human review."""
        return sum(1 for entry in self.entries if entry.requires_human_review)

    def blocker_count(self) -> int:
        """Return the number of entries blocking autonomous progress."""
        return sum(1 for entry in self.entries if entry.blocks_progress())

    def has_blocker(self) -> bool:
        """Return whether this docket contains any blocking entry."""
        return self.blocker_count() > 0

    def referenced_digests(self) -> tuple[DigestRecord, ...]:
        """Return all digests referenced by docket entries."""
        return tuple(
            entry.reference_digest
            for entry in self.entries
            if entry.reference_digest is not None
        )

    def to_artifact(self) -> AgentArtifact:
        """Convert this packet into a shared runtime artifact."""
        return AgentArtifact.create(
            cycle=self.cycle,
            role=AgentRole.CLERK,
            kind=AgentArtifactKind.DOSSIER_ENTRY,
            summary=f"IX-Clerk recorded {len(self.entries)} docket entrie(s).",
            referenced_digests=self.referenced_digests(),
            data=self.to_payload(),
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible docket packet representation."""
        entries_payload: JsonArray = []
        for entry in self.entries:
            entries_payload.append(entry.to_payload())

        return {
            "packet_id": self.packet_id.value,
            "cycle": self.cycle,
            "docket_summary": self.docket_summary,
            "entries": entries_payload,
            "human_review_count": self.human_review_count(),
            "blocker_count": self.blocker_count(),
            "has_blocker": self.has_blocker(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this docket packet."""
        return DigestRecord.from_payload(self.to_payload())
