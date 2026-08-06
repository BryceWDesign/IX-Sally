"""Attention, belief, hypothesis, goal, and executive workspace records."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class WorkspaceItemKind(StrEnum):
    """Kinds of information admitted to the cognitive workspace."""

    OBSERVATION = "observation"
    BELIEF = "belief"
    HYPOTHESIS = "hypothesis"
    GOAL = "goal"
    QUESTION = "question"
    RISK = "risk"


class WorkspaceItemStatus(StrEnum):
    """Lifecycle state of one workspace item."""

    ACTIVE = "active"
    SATISFIED = "satisfied"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


@dataclass(frozen=True, slots=True)
class WorkspaceItem:
    """One confidence-bounded item with explicit evidence and salience."""

    item_id: CanonicalKey
    kind: WorkspaceItemKind
    content: str
    confidence: float
    salience: float
    status: WorkspaceItemStatus = WorkspaceItemStatus.ACTIVE
    evidence_digests: tuple[DigestRecord, ...] = ()
    parent_ids: tuple[CanonicalKey, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        item_id: str,
        kind: WorkspaceItemKind,
        content: str,
        confidence: float,
        salience: float,
        status: WorkspaceItemStatus = WorkspaceItemStatus.ACTIVE,
        evidence_digests: Iterable[DigestRecord] = (),
        parent_ids: Iterable[str] = (),
    ) -> WorkspaceItem:
        """Create an item while preserving uncertainty and provenance."""
        for field_name, value in {
            "confidence": confidence,
            "salience": salience,
        }.items():
            if not 0.0 <= value <= 1.0:
                raise FoundationError(f"workspace {field_name} must be between 0 and 1")
        evidence = tuple(evidence_digests)
        for digest in evidence:
            digest.require_algorithm("sha256")
        if kind is WorkspaceItemKind.OBSERVATION and confidence < 1.0:
            raise FoundationError("direct observation confidence must be 1.0")
        return cls(
            item_id=CanonicalKey.from_text(item_id, field_name="item_id"),
            kind=kind,
            content=require_text(content, field_name="content"),
            confidence=confidence,
            salience=salience,
            status=status,
            evidence_digests=evidence,
            parent_ids=tuple(
                sorted(
                    {
                        CanonicalKey.from_text(parent, field_name="parent_id")
                        for parent in parent_ids
                    },
                    key=lambda item: item.value,
                )
            ),
        )

    def attention_score(self) -> float:
        """Return the deterministic attention score for this item."""
        status_weight = 1.0 if self.status is WorkspaceItemStatus.ACTIVE else 0.25
        kind_weight = {
            WorkspaceItemKind.RISK: 1.0,
            WorkspaceItemKind.GOAL: 0.95,
            WorkspaceItemKind.QUESTION: 0.9,
            WorkspaceItemKind.OBSERVATION: 0.85,
            WorkspaceItemKind.HYPOTHESIS: 0.8,
            WorkspaceItemKind.BELIEF: 0.75,
        }[self.kind]
        score = status_weight * kind_weight * (0.65 * self.salience + 0.35 * self.confidence)
        return round(score, 12)

    def to_payload(self) -> JsonObject:
        """Return a canonical workspace-item payload."""
        evidence: JsonArray = [
            {"algorithm": digest.algorithm, "value": digest.value}
            for digest in self.evidence_digests
        ]
        parents: JsonArray = [parent.value for parent in self.parent_ids]
        return {
            "item_id": self.item_id.value,
            "kind": self.kind.value,
            "content": self.content,
            "confidence": self.confidence,
            "salience": self.salience,
            "attention_score": self.attention_score(),
            "status": self.status.value,
            "evidence_digests": evidence,
            "parent_ids": parents,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic item identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class CognitiveWorkspace:
    """Immutable bounded workspace with deterministic attention selection."""

    items: tuple[WorkspaceItem, ...] = ()
    capacity: int = 32

    def __post_init__(self) -> None:
        """Enforce capacity and identifier uniqueness."""
        if self.capacity <= 0:
            raise FoundationError("workspace capacity must be positive")
        if len(self.items) > self.capacity:
            raise FoundationError("workspace exceeds configured capacity")
        identifiers = [item.item_id.value for item in self.items]
        if len(identifiers) != len(set(identifiers)):
            raise FoundationError("workspace contains duplicate item identifiers")

    def admit(self, item: WorkspaceItem) -> CognitiveWorkspace:
        """Return a workspace with one item admitted and low-attention overflow evicted."""
        if any(existing.item_id == item.item_id for existing in self.items):
            raise FoundationError(f"workspace item already exists: {item.item_id.value}")
        candidates = (*self.items, item)
        ordered = tuple(
            sorted(
                candidates,
                key=lambda candidate: (
                    -candidate.attention_score(),
                    candidate.item_id.value,
                ),
            )
        )
        retained = ordered[: self.capacity]
        return CognitiveWorkspace(
            items=tuple(sorted(retained, key=lambda candidate: candidate.item_id.value)),
            capacity=self.capacity,
        )

    def replace(self, item: WorkspaceItem) -> CognitiveWorkspace:
        """Replace one existing item without changing unrelated state."""
        if not any(existing.item_id == item.item_id for existing in self.items):
            raise FoundationError(f"unknown workspace item: {item.item_id.value}")
        return CognitiveWorkspace(
            items=tuple(
                item if existing.item_id == item.item_id else existing for existing in self.items
            ),
            capacity=self.capacity,
        )

    def focus(self, limit: int = 5) -> tuple[WorkspaceItem, ...]:
        """Return the highest-attention active items."""
        if limit <= 0:
            raise FoundationError("workspace focus limit must be positive")
        active = (item for item in self.items if item.status is WorkspaceItemStatus.ACTIVE)
        return tuple(
            sorted(
                active,
                key=lambda item: (-item.attention_score(), item.item_id.value),
            )[:limit]
        )

    def goals(self) -> tuple[WorkspaceItem, ...]:
        """Return active goals in attention order."""
        return tuple(
            item for item in self.focus(limit=self.capacity) if item.kind is WorkspaceItemKind.GOAL
        )

    def to_payload(self) -> JsonObject:
        """Return a deterministic workspace payload."""
        items: JsonArray = [
            item.to_payload()
            for item in sorted(
                self.items,
                key=lambda candidate: candidate.item_id.value,
            )
        ]
        focus: JsonArray = [item.item_id.value for item in self.focus()]
        return {
            "capacity": self.capacity,
            "item_count": len(self.items),
            "items": items,
            "focus": focus,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic workspace identity."""
        return DigestRecord.from_payload(self.to_payload())
