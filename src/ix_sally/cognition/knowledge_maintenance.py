"""Evidence-driven lifelong knowledge maintenance.

This layer makes memory active rather than append-only: repeated contextual contradictions
can split an over-broad concept, weak contradicted concepts can be retired, and redundant
items can be merged through the existing ontology restructuring machinery.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from ix_sally.cognition.lifelong import KnowledgeItem, LifelongKnowledgeStore
from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class ContextualKnowledgeEvidence:
    concept_id: str
    context_id: str
    predicted: bool
    actual: bool
    confidence: float = 1.0

    def __post_init__(self) -> None:
        require_text(self.concept_id, field_name="concept_id")
        require_text(self.context_id, field_name="context_id")
        if not 0.0 <= self.confidence <= 1.0:
            raise FoundationError("contextual evidence confidence must be between zero and one")


@dataclass(frozen=True, slots=True)
class KnowledgeMaintenanceReport:
    store: LifelongKnowledgeStore
    split_concepts: tuple[str, ...]
    retired_concepts: tuple[str, ...]
    created_context_concepts: tuple[str, ...]
    contradiction_resolved: bool

    def to_payload(self) -> JsonObject:
        return {
            "store": self.store.to_payload(),
            "split_concepts": list(self.split_concepts),
            "retired_concepts": list(self.retired_concepts),
            "created_context_concepts": list(self.created_context_concepts),
            "contradiction_resolved": self.contradiction_resolved,
        }


class KnowledgeMaintenanceEngine:
    """Split over-broad concepts by context and retire unsupported concepts."""

    def reconcile(
        self,
        store: LifelongKnowledgeStore,
        *,
        evidence: Iterable[ContextualKnowledgeEvidence],
        split_minimum_per_context: int = 2,
        context_accuracy_gap: float = 0.60,
        retire_confidence_below: float = 0.20,
        retire_utility_below: float = 0.20,
        retire_contradictions_at: int = 3,
    ) -> KnowledgeMaintenanceReport:
        items = tuple(evidence)
        evidence_by_concept: dict[str, list[ContextualKnowledgeEvidence]] = {}
        for item in items:
            evidence_by_concept.setdefault(item.concept_id, []).append(item)
        updated = store
        split: list[str] = []
        children: list[str] = []
        retired: list[str] = []

        for concept_id, concept_evidence in sorted(evidence_by_concept.items()):
            source = next((item for item in updated.items if item.concept_id == concept_id), None)
            if source is None or source.superseded_by is not None:
                continue
            by_context: dict[str, list[ContextualKnowledgeEvidence]] = {}
            for observation in concept_evidence:
                by_context.setdefault(observation.context_id, []).append(observation)
            qualified = {
                context: observations
                for context, observations in by_context.items()
                if len(observations) >= split_minimum_per_context
            }
            if len(qualified) < 2:
                continue
            accuracies = {
                context: sum(obs.predicted == obs.actual for obs in observations) / len(observations)
                for context, observations in qualified.items()
            }
            if max(accuracies.values()) - min(accuracies.values()) < context_accuracy_gap:
                continue
            family_digest = DigestRecord.from_payload(
                {"source": concept_id, "contexts": sorted(accuracies.items())}
            )
            family_id = f"context-family-{family_digest.value[:16]}"
            replaced: list[KnowledgeItem] = []
            for item in updated.items:
                if item.concept_id == concept_id:
                    replaced.append(replace(item, superseded_by=family_id))
                else:
                    replaced.append(item)
            family = KnowledgeItem(
                concept_id=family_id,
                content_digest=family_digest,
                confidence=max(accuracies.values()),
                utility=source.utility,
                generation=updated.generation,
            )
            replaced.append(family)
            for context, accuracy in sorted(accuracies.items()):
                child_digest = DigestRecord.from_payload(
                    {"parent": concept_id, "context": context, "empirical_accuracy": accuracy}
                )
                child_id = f"{family_id}::{context}"
                children.append(child_id)
                replaced.append(
                    KnowledgeItem(
                        concept_id=child_id,
                        content_digest=child_digest,
                        confidence=accuracy,
                        utility=source.utility * accuracy,
                        generation=updated.generation,
                    )
                )
            updated = LifelongKnowledgeStore(tuple(sorted(replaced, key=lambda item: item.concept_id)), updated.generation)
            split.append(concept_id)

        retained: list[KnowledgeItem] = []
        for item in updated.items:
            should_retire = (
                item.superseded_by is None
                and item.confidence < retire_confidence_below
                and item.utility < retire_utility_below
                and item.contradiction_count >= retire_contradictions_at
            )
            if should_retire:
                retired.append(item.concept_id)
            else:
                retained.append(item)
        updated = LifelongKnowledgeStore(tuple(retained), updated.generation)
        return KnowledgeMaintenanceReport(
            store=updated,
            split_concepts=tuple(split),
            retired_concepts=tuple(retired),
            created_context_concepts=tuple(children),
            contradiction_resolved=bool(split or retired),
        )
