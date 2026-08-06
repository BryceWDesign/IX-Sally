"""Working, episodic, semantic, and procedural memory with truth boundaries."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonArray, JsonObject, JsonValue
from ix_sally.foundation import CanonicalKey, FoundationError, require_text

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class MemoryLayer(StrEnum):
    """Distinct stores used by the active memory system."""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class ActiveMemoryStatus(StrEnum):
    """Truth and lifecycle status of one active memory entry."""

    CANDIDATE = "candidate"
    VERIFIED = "verified"
    STALE = "stale"
    CONTRADICTED = "contradicted"
    QUARANTINED = "quarantined"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class ActiveMemoryEntry:
    """One versioned memory entry with content, confidence, and provenance."""

    memory_id: CanonicalKey
    layer: MemoryLayer
    content: str
    confidence: float
    status: ActiveMemoryStatus
    sequence: int
    evidence_digests: tuple[DigestRecord, ...] = ()
    source_ids: tuple[CanonicalKey, ...] = ()
    tags: tuple[CanonicalKey, ...] = ()
    reason: str | None = None

    @classmethod
    def create(
        cls,
        *,
        memory_id: str,
        layer: MemoryLayer,
        content: str,
        confidence: float,
        status: ActiveMemoryStatus,
        sequence: int,
        evidence_digests: Iterable[DigestRecord] = (),
        source_ids: Iterable[str] = (),
        tags: Iterable[str] = (),
        reason: str | None = None,
    ) -> ActiveMemoryEntry:
        """Create a memory entry without silently promoting content to truth."""
        if not 0.0 <= confidence <= 1.0:
            raise FoundationError("active memory confidence must be between 0 and 1")
        if sequence < 0:
            raise FoundationError("active memory sequence must not be negative")
        evidence = tuple(evidence_digests)
        for digest in evidence:
            digest.require_algorithm("sha256")
        if status is ActiveMemoryStatus.VERIFIED and not evidence:
            raise FoundationError("verified active memory requires evidence")
        if (
            status
            in {
                ActiveMemoryStatus.CONTRADICTED,
                ActiveMemoryStatus.QUARANTINED,
                ActiveMemoryStatus.RETIRED,
            }
            and not reason
        ):
            raise FoundationError("inactive active memory requires a reason")
        return cls(
            memory_id=CanonicalKey.from_text(memory_id, field_name="memory_id"),
            layer=layer,
            content=require_text(content, field_name="content"),
            confidence=confidence,
            status=status,
            sequence=sequence,
            evidence_digests=evidence,
            source_ids=tuple(
                sorted(
                    {
                        CanonicalKey.from_text(source_id, field_name="source_id")
                        for source_id in source_ids
                    },
                    key=lambda item: item.value,
                )
            ),
            tags=tuple(
                sorted(
                    {CanonicalKey.from_text(tag, field_name="tag") for tag in tags},
                    key=lambda item: item.value,
                )
            ),
            reason=require_text(reason, field_name="reason") if reason else None,
        )

    def is_retrievable_truth(self) -> bool:
        """Return whether this entry may support a factual answer."""
        return self.status is ActiveMemoryStatus.VERIFIED

    def tokens(self) -> frozenset[str]:
        """Return normalized lexical tokens used by deterministic retrieval."""
        return frozenset(_TOKEN_PATTERN.findall(self.content.lower()))

    def to_payload(self) -> JsonObject:
        """Return a canonical active-memory payload."""
        evidence: JsonArray = [
            {"algorithm": digest.algorithm, "value": digest.value}
            for digest in self.evidence_digests
        ]
        sources: JsonArray = [source.value for source in self.source_ids]
        tags: JsonArray = [tag.value for tag in self.tags]
        return {
            "memory_id": self.memory_id.value,
            "layer": self.layer.value,
            "content": self.content,
            "confidence": self.confidence,
            "status": self.status.value,
            "sequence": self.sequence,
            "evidence_digests": evidence,
            "source_ids": sources,
            "tags": tags,
            "reason": self.reason,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic entry identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class MemoryRetrieval:
    """One scored memory retrieval result."""

    entry: ActiveMemoryEntry
    lexical_score: float
    confidence_score: float
    recency_score: float
    total_score: float

    def to_payload(self) -> JsonObject:
        """Return a deterministic retrieval receipt."""
        return {
            "entry_digest": {
                "algorithm": self.entry.digest().algorithm,
                "value": self.entry.digest().value,
            },
            "lexical_score": self.lexical_score,
            "confidence_score": self.confidence_score,
            "recency_score": self.recency_score,
            "total_score": self.total_score,
        }


@dataclass(frozen=True, slots=True)
class ActiveMemoryStore:
    """Immutable multi-layer memory store with bounded deterministic retrieval."""

    entries: tuple[ActiveMemoryEntry, ...] = ()

    def __post_init__(self) -> None:
        """Reject duplicate identifiers and non-monotonic versions per identity."""
        identifiers = [entry.memory_id.value for entry in self.entries]
        if len(identifiers) != len(set(identifiers)):
            raise FoundationError("active memory contains duplicate identifiers")

    def append(self, entry: ActiveMemoryEntry) -> ActiveMemoryStore:
        """Return a store with one unique entry appended."""
        if any(existing.memory_id == entry.memory_id for existing in self.entries):
            raise FoundationError(f"active memory already exists: {entry.memory_id.value}")
        return ActiveMemoryStore((*self.entries, entry))

    def require(self, memory_id: str) -> ActiveMemoryEntry:
        """Return one memory entry by canonical identifier."""
        requested = CanonicalKey.from_text(memory_id, field_name="memory_id")
        for entry in self.entries:
            if entry.memory_id == requested:
                return entry
        raise FoundationError(f"unknown active memory: {requested.value}")

    def replace(self, entry: ActiveMemoryEntry) -> ActiveMemoryStore:
        """Replace an entry while requiring a strictly later sequence."""
        current = self.require(entry.memory_id.value)
        if entry.sequence <= current.sequence:
            raise FoundationError("active memory replacement sequence must increase")
        return ActiveMemoryStore(
            tuple(
                entry if existing.memory_id == entry.memory_id else existing
                for existing in self.entries
            )
        )

    def retrieve(
        self,
        query: str,
        *,
        layers: Iterable[MemoryLayer] = tuple(MemoryLayer),
        limit: int = 5,
        truth_only: bool = False,
    ) -> tuple[MemoryRetrieval, ...]:
        """Retrieve entries using transparent lexical, confidence, and recency scores."""
        normalized_query = require_text(query, field_name="query")
        if limit <= 0:
            raise FoundationError("memory retrieval limit must be positive")
        layer_set = frozenset(layers)
        query_tokens = frozenset(_TOKEN_PATTERN.findall(normalized_query.lower()))
        max_sequence = max((entry.sequence for entry in self.entries), default=0)
        results: list[MemoryRetrieval] = []
        for entry in self.entries:
            if entry.layer not in layer_set:
                continue
            if truth_only and not entry.is_retrievable_truth():
                continue
            overlap = len(query_tokens & entry.tokens())
            union = len(query_tokens | entry.tokens())
            lexical = overlap / union if union else 0.0
            recency = entry.sequence / max_sequence if max_sequence else 0.0
            total = round(0.55 * lexical + 0.3 * entry.confidence + 0.15 * recency, 12)
            results.append(
                MemoryRetrieval(
                    entry=entry,
                    lexical_score=round(lexical, 12),
                    confidence_score=entry.confidence,
                    recency_score=round(recency, 12),
                    total_score=total,
                )
            )
        return tuple(
            sorted(
                results,
                key=lambda result: (
                    -result.total_score,
                    result.entry.memory_id.value,
                ),
            )[:limit]
        )

    def consolidate(
        self,
        *,
        memory_id: str,
        source_ids: Iterable[str],
        content: str,
        evidence_digests: Iterable[DigestRecord],
        confidence: float,
    ) -> ActiveMemoryStore:
        """Create semantic memory from verified source entries only."""
        normalized_sources = tuple(source_ids)
        if not normalized_sources:
            raise FoundationError("memory consolidation requires source entries")
        sources = tuple(self.require(source_id) for source_id in normalized_sources)
        if any(not source.is_retrievable_truth() for source in sources):
            raise FoundationError("memory consolidation requires verified source entries")
        sequence = max((entry.sequence for entry in self.entries), default=-1) + 1
        consolidated = ActiveMemoryEntry.create(
            memory_id=memory_id,
            layer=MemoryLayer.SEMANTIC,
            content=content,
            confidence=confidence,
            status=ActiveMemoryStatus.VERIFIED,
            sequence=sequence,
            evidence_digests=evidence_digests,
            source_ids=normalized_sources,
            tags=("consolidated",),
        )
        return self.append(consolidated)

    def to_payload(self) -> JsonObject:
        """Return a canonical memory-store payload."""
        entries: JsonArray = [
            entry.to_payload()
            for entry in sorted(
                self.entries,
                key=lambda candidate: candidate.memory_id.value,
            )
        ]
        layer_counts: dict[str, JsonValue] = {
            layer.value: sum(1 for entry in self.entries if entry.layer is layer)
            for layer in MemoryLayer
        }
        return {
            "entry_count": len(self.entries),
            "layer_counts": layer_counts,
            "entries": entries,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic store identity."""
        return DigestRecord.from_payload(self.to_payload())
