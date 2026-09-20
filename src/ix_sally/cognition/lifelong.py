"""Lifelong learning, consolidation, restructuring, transfer, and curriculum choice."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace

from ix_sally.cognition.metacognition import SelfModel
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class KnowledgeItem:
    """One persistent learned item with usage, contradiction, and revision evidence."""

    concept_id: str
    content_digest: DigestRecord
    confidence: float
    utility: float
    use_count: int = 0
    contradiction_count: int = 0
    generation: int = 0
    superseded_by: str | None = None

    def __post_init__(self) -> None:
        require_text(self.concept_id, field_name="concept_id")
        self.content_digest.require_algorithm("sha256")
        if not 0.0 <= self.confidence <= 1.0 or not 0.0 <= self.utility <= 1.0:
            raise FoundationError("knowledge confidence and utility must be between zero and one")
        if self.use_count < 0 or self.contradiction_count < 0 or self.generation < 0:
            raise FoundationError("knowledge counters must not be negative")
        if self.superseded_by is not None:
            require_text(self.superseded_by, field_name="superseded_by")

    def to_payload(self) -> JsonObject:
        return {
            "concept_id": self.concept_id,
            "content_digest": {
                "algorithm": self.content_digest.algorithm,
                "value": self.content_digest.value,
            },
            "confidence": self.confidence,
            "utility": self.utility,
            "use_count": self.use_count,
            "contradiction_count": self.contradiction_count,
            "generation": self.generation,
            "superseded_by": self.superseded_by,
        }


@dataclass(frozen=True, slots=True)
class LifelongKnowledgeStore:
    """Immutable persistent knowledge with consolidation, revision, and selective forgetting."""

    items: tuple[KnowledgeItem, ...] = ()
    generation: int = 0

    def __post_init__(self) -> None:
        identifiers = [item.concept_id for item in self.items]
        if len(identifiers) != len(set(identifiers)):
            raise FoundationError("lifelong knowledge contains duplicate concept ids")
        if self.generation < 0:
            raise FoundationError("knowledge generation must not be negative")

    def integrate(self, item: KnowledgeItem) -> LifelongKnowledgeStore:
        retained = tuple(
            existing for existing in self.items if existing.concept_id != item.concept_id
        )
        normalized = replace(item, generation=self.generation)
        return LifelongKnowledgeStore(
            items=tuple(sorted((*retained, normalized), key=lambda value: value.concept_id)),
            generation=self.generation,
        )

    def record_use(self, concept_id: str, *, successful: bool) -> LifelongKnowledgeStore:
        found = False
        updated: list[KnowledgeItem] = []
        for item in self.items:
            if item.concept_id != concept_id:
                updated.append(item)
                continue
            found = True
            confidence = item.confidence
            utility = item.utility
            contradictions = item.contradiction_count
            if successful:
                confidence = min(1.0, confidence + 0.05)
                utility = min(1.0, utility + 0.04)
            else:
                confidence = max(0.0, confidence - 0.15)
                utility = max(0.0, utility - 0.08)
                contradictions += 1
            updated.append(
                replace(
                    item,
                    confidence=round(confidence, 12),
                    utility=round(utility, 12),
                    use_count=item.use_count + 1,
                    contradiction_count=contradictions,
                )
            )
        if not found:
            raise FoundationError(f"unknown lifelong concept: {concept_id}")
        return LifelongKnowledgeStore(tuple(updated), self.generation)

    def advance_generation(self) -> LifelongKnowledgeStore:
        return LifelongKnowledgeStore(self.items, self.generation + 1)

    def consolidate(
        self, *, minimum_score: float = 0.25, protected_utility: float = 0.75
    ) -> LifelongKnowledgeStore:
        """Forget weak, unused stale items while retaining useful or validated knowledge."""
        if not 0.0 <= minimum_score <= 1.0 or not 0.0 <= protected_utility <= 1.0:
            raise FoundationError("consolidation thresholds must be between zero and one")
        retained: list[KnowledgeItem] = []
        for item in self.items:
            age = max(0, self.generation - item.generation)
            retention = (
                0.45 * item.confidence
                + 0.35 * item.utility
                + 0.20 * min(1.0, item.use_count / 5.0)
                - min(0.35, age * 0.03)
                - min(0.30, item.contradiction_count * 0.08)
            )
            if item.utility >= protected_utility or retention >= minimum_score:
                retained.append(item)
        return LifelongKnowledgeStore(tuple(retained), self.generation)

    def to_payload(self) -> JsonObject:
        items: JsonArray = [item.to_payload() for item in self.items]
        return {"generation": self.generation, "items": items}

    def digest(self) -> DigestRecord:
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class PredictionSignature:
    """Behavioral signature used to discover redundant or higher-order concepts."""

    concept_id: str
    predictions: tuple[bool, ...]

    def __post_init__(self) -> None:
        require_text(self.concept_id, field_name="concept_id")
        if not self.predictions:
            raise FoundationError("prediction signature cannot be empty")


@dataclass(frozen=True, slots=True)
class RestructuredConcept:
    """A higher-order abstraction replacing multiple behaviorally redundant concepts."""

    concept_id: str
    member_ids: tuple[str, ...]
    signature: tuple[bool, ...]

    def __post_init__(self) -> None:
        require_text(self.concept_id, field_name="concept_id")
        if len(self.member_ids) < 2:
            raise FoundationError("restructured concept requires at least two members")


class OntologyRestructurer:
    """Compress concepts that make identical predictions into a higher abstraction."""

    def restructure(
        self, signatures: Iterable[PredictionSignature]
    ) -> tuple[RestructuredConcept, ...]:
        groups: dict[tuple[bool, ...], list[str]] = {}
        for item in signatures:
            groups.setdefault(item.predictions, []).append(item.concept_id)
        results: list[RestructuredConcept] = []
        for signature, members in sorted(groups.items(), key=lambda item: item[0]):
            if len(members) < 2:
                continue
            members_payload: JsonArray = []
            members_payload.extend(sorted(members))
            signature_payload: JsonArray = []
            signature_payload.extend(signature)
            identity = DigestRecord.from_payload(
                {"members": members_payload, "signature": signature_payload}
            )
            results.append(
                RestructuredConcept(
                    concept_id=f"abstraction-{identity.value[:16]}",
                    member_ids=tuple(sorted(members)),
                    signature=signature,
                )
            )
        return tuple(results)

    def apply_to_store(
        self,
        store: LifelongKnowledgeStore,
        abstraction: RestructuredConcept,
    ) -> LifelongKnowledgeStore:
        members_payload: JsonArray = []
        members_payload.extend(abstraction.member_ids)
        signature_payload: JsonArray = []
        signature_payload.extend(abstraction.signature)
        identity = DigestRecord.from_payload(
            {"members": members_payload, "signature": signature_payload}
        )
        updated: list[KnowledgeItem] = []
        member_confidences: list[float] = []
        member_utilities: list[float] = []
        for item in store.items:
            if item.concept_id in abstraction.member_ids:
                member_confidences.append(item.confidence)
                member_utilities.append(item.utility)
                updated.append(replace(item, superseded_by=abstraction.concept_id))
            else:
                updated.append(item)
        if len(member_confidences) != len(abstraction.member_ids):
            raise FoundationError("ontology restructuring members are missing from lifelong store")
        updated.append(
            KnowledgeItem(
                concept_id=abstraction.concept_id,
                content_digest=identity,
                confidence=sum(member_confidences) / len(member_confidences),
                utility=sum(member_utilities) / len(member_utilities),
                generation=store.generation,
            )
        )
        return LifelongKnowledgeStore(
            tuple(sorted(updated, key=lambda item: item.concept_id)), store.generation
        )


@dataclass(frozen=True, slots=True)
class DomainAdapter:
    """Surface-domain adapter for testing whether an abstract rule transfers."""

    domain_id: str
    encode: Callable[[object], int]
    decode: Callable[[int], object]

    def __post_init__(self) -> None:
        require_text(self.domain_id, field_name="domain_id")


@dataclass(frozen=True, slots=True)
class AbstractTransitionRule:
    """A domain-neutral affine relation learned once and reusable through adapters."""

    multiplier: int
    offset: int
    source_domain: str

    def apply(self, value: object, adapter: DomainAdapter) -> object:
        encoded = adapter.encode(value)
        return adapter.decode(self.multiplier * encoded + self.offset)


class StructuralAnalogyEngine:
    """Learn a simple structural rule in one domain and transfer it to another surface domain."""

    def learn_affine(
        self,
        *,
        examples: Iterable[tuple[object, object]],
        adapter: DomainAdapter,
        multiplier_bound: int = 4,
        offset_bound: int = 8,
    ) -> AbstractTransitionRule:
        pairs = tuple(examples)
        if not pairs:
            raise FoundationError("structural transfer requires examples")
        encoded = tuple((adapter.encode(left), adapter.encode(right)) for left, right in pairs)
        for multiplier in range(-multiplier_bound, multiplier_bound + 1):
            for offset in range(-offset_bound, offset_bound + 1):
                if all(multiplier * left + offset == right for left, right in encoded):
                    return AbstractTransitionRule(multiplier, offset, adapter.domain_id)
        raise FoundationError("no affine structural rule found within bounds")

    def evaluate_transfer(
        self,
        rule: AbstractTransitionRule,
        *,
        examples: Iterable[tuple[object, object]],
        adapter: DomainAdapter,
    ) -> float:
        pairs = tuple(examples)
        if not pairs:
            raise FoundationError("transfer evaluation requires examples")
        correct = sum(rule.apply(left, adapter) == right for left, right in pairs)
        return correct / len(pairs)


@dataclass(frozen=True, slots=True)
class CurriculumChoice:
    """Self-directed choice of what capability to practice next."""

    capability_id: str
    score: float
    reason: str


class SelfDirectedCurriculum:
    """Choose the next learning target from measured weakness, uncertainty, and opportunity."""

    def choose(
        self,
        *,
        self_model: SelfModel,
        uncertainty: dict[str, float] | None = None,
        opportunity: dict[str, float] | None = None,
    ) -> CurriculumChoice:
        if not self_model.measures:
            raise FoundationError("self-directed curriculum requires capability measures")
        uncertainty = uncertainty or {}
        opportunity = opportunity or {}
        choices: list[CurriculumChoice] = []
        for measure in self_model.measures:
            capability = measure.capability_id.value
            weakness = 1.0 - measure.score
            uncertain = min(1.0, max(0.0, uncertainty.get(capability, 0.0)))
            potential = min(1.0, max(0.0, opportunity.get(capability, 0.5)))
            score = 0.55 * weakness + 0.25 * uncertain + 0.20 * potential
            choices.append(
                CurriculumChoice(
                    capability_id=capability,
                    score=round(score, 12),
                    reason=(
                        f"weakness={weakness:.3f}; uncertainty={uncertain:.3f}; "
                        f"learning-opportunity={potential:.3f}"
                    ),
                )
            )
        return max(
            choices, key=lambda item: (item.score, tuple(-ord(ch) for ch in item.capability_id))
        )
