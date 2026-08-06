"""Evidence-aware entities, facts, causal rules, predictions, and counterfactuals."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.cognition.values import CognitiveValue
from ix_sally.digest import DigestRecord, JsonArray, JsonObject, JsonValue
from ix_sally.foundation import CanonicalKey, FoundationError


class FactStatus(StrEnum):
    """Epistemic status of a fact represented in the world model."""

    OBSERVED = "observed"
    INFERRED = "inferred"
    PREDICTED = "predicted"
    HYPOTHETICAL = "hypothetical"
    CONTRADICTED = "contradicted"


@dataclass(frozen=True, slots=True)
class WorldFact:
    """One subject-predicate-object assertion with explicit epistemic status."""

    fact_id: CanonicalKey
    subject: CanonicalKey
    predicate: CanonicalKey
    value: CognitiveValue
    status: FactStatus
    confidence: float
    evidence_digests: tuple[DigestRecord, ...] = ()
    derived_from: tuple[CanonicalKey, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        fact_id: str,
        subject: str,
        predicate: str,
        value: CognitiveValue,
        status: FactStatus,
        confidence: float,
        evidence_digests: Iterable[DigestRecord] = (),
        derived_from: Iterable[str] = (),
    ) -> WorldFact:
        """Create a fact without collapsing observation, inference, and prediction."""
        if not 0.0 <= confidence <= 1.0:
            raise FoundationError("world fact confidence must be between 0 and 1")
        evidence = tuple(evidence_digests)
        for digest in evidence:
            digest.require_algorithm("sha256")
        if status is FactStatus.OBSERVED and not evidence:
            raise FoundationError("observed world fact requires evidence")
        return cls(
            fact_id=CanonicalKey.from_text(fact_id, field_name="fact_id"),
            subject=CanonicalKey.from_text(subject, field_name="subject"),
            predicate=CanonicalKey.from_text(predicate, field_name="predicate"),
            value=value,
            status=status,
            confidence=confidence,
            evidence_digests=evidence,
            derived_from=tuple(
                sorted(
                    {
                        CanonicalKey.from_text(item, field_name="derived_from")
                        for item in derived_from
                    },
                    key=lambda item: item.value,
                )
            ),
        )

    def key(self) -> tuple[str, str]:
        """Return the subject-predicate state key."""
        return (self.subject.value, self.predicate.value)

    def to_payload(self) -> JsonObject:
        """Return a canonical fact payload."""
        evidence: JsonArray = [
            {"algorithm": digest.algorithm, "value": digest.value}
            for digest in self.evidence_digests
        ]
        derived: JsonArray = [item.value for item in self.derived_from]
        return {
            "fact_id": self.fact_id.value,
            "subject": self.subject.value,
            "predicate": self.predicate.value,
            "value": self.value.to_payload(),
            "status": self.status.value,
            "confidence": self.confidence,
            "evidence_digests": evidence,
            "derived_from": derived,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic fact identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class FactPattern:
    """One exact match condition used by causal and planning rules."""

    subject: CanonicalKey
    predicate: CanonicalKey
    value: CognitiveValue

    @classmethod
    def create(
        cls,
        *,
        subject: str,
        predicate: str,
        value: CognitiveValue,
    ) -> FactPattern:
        """Create one canonical fact pattern."""
        return cls(
            subject=CanonicalKey.from_text(subject, field_name="subject"),
            predicate=CanonicalKey.from_text(predicate, field_name="predicate"),
            value=value,
        )

    def matches(self, facts: Mapping[tuple[str, str], WorldFact]) -> bool:
        """Return whether the current state exactly satisfies this pattern."""
        fact = facts.get((self.subject.value, self.predicate.value))
        return (
            fact is not None
            and fact.value == self.value
            and fact.status is not FactStatus.CONTRADICTED
        )

    def to_payload(self) -> JsonObject:
        """Return a canonical pattern payload."""
        return {
            "subject": self.subject.value,
            "predicate": self.predicate.value,
            "value": self.value.to_payload(),
        }


@dataclass(frozen=True, slots=True)
class CausalRule:
    """One transparent deterministic implication over exact fact patterns."""

    rule_id: CanonicalKey
    conditions: tuple[FactPattern, ...]
    effect_subject: CanonicalKey
    effect_predicate: CanonicalKey
    effect_value: CognitiveValue
    confidence: float
    evidence_digests: tuple[DigestRecord, ...]

    @classmethod
    def create(
        cls,
        *,
        rule_id: str,
        conditions: Iterable[FactPattern],
        effect_subject: str,
        effect_predicate: str,
        effect_value: CognitiveValue,
        confidence: float,
        evidence_digests: Iterable[DigestRecord],
    ) -> CausalRule:
        """Create a causal rule that is evidence-bound and non-empty."""
        normalized_conditions = tuple(conditions)
        evidence = tuple(evidence_digests)
        if not normalized_conditions:
            raise FoundationError("causal rule requires at least one condition")
        if not evidence:
            raise FoundationError("causal rule requires supporting evidence")
        if not 0.0 <= confidence <= 1.0:
            raise FoundationError("causal rule confidence must be between 0 and 1")
        for digest in evidence:
            digest.require_algorithm("sha256")
        return cls(
            rule_id=CanonicalKey.from_text(rule_id, field_name="rule_id"),
            conditions=normalized_conditions,
            effect_subject=CanonicalKey.from_text(
                effect_subject,
                field_name="effect_subject",
            ),
            effect_predicate=CanonicalKey.from_text(
                effect_predicate,
                field_name="effect_predicate",
            ),
            effect_value=effect_value,
            confidence=confidence,
            evidence_digests=evidence,
        )

    def to_payload(self) -> JsonObject:
        """Return a canonical causal-rule payload."""
        conditions: JsonArray = [condition.to_payload() for condition in self.conditions]
        evidence: JsonArray = [
            {"algorithm": digest.algorithm, "value": digest.value}
            for digest in self.evidence_digests
        ]
        return {
            "rule_id": self.rule_id.value,
            "conditions": conditions,
            "effect_subject": self.effect_subject.value,
            "effect_predicate": self.effect_predicate.value,
            "effect_value": self.effect_value.to_payload(),
            "confidence": self.confidence,
            "evidence_digests": evidence,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic rule identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class WorldModel:
    """Immutable fact state and causal model with deterministic inference."""

    facts: tuple[WorldFact, ...] = ()
    rules: tuple[CausalRule, ...] = ()

    def __post_init__(self) -> None:
        """Reject duplicate fact and rule identifiers."""
        fact_ids = [fact.fact_id.value for fact in self.facts]
        rule_ids = [rule.rule_id.value for rule in self.rules]
        if len(fact_ids) != len(set(fact_ids)):
            raise FoundationError("world model contains duplicate fact identifiers")
        if len(rule_ids) != len(set(rule_ids)):
            raise FoundationError("world model contains duplicate rule identifiers")

    def state(self) -> dict[tuple[str, str], WorldFact]:
        """Return the latest fact per subject-predicate key by tuple order."""
        state: dict[tuple[str, str], WorldFact] = {}
        for fact in self.facts:
            state[fact.key()] = fact
        return state

    def observe(self, fact: WorldFact) -> WorldModel:
        """Append one fact while requiring a unique identity."""
        if any(existing.fact_id == fact.fact_id for existing in self.facts):
            raise FoundationError(f"world fact already exists: {fact.fact_id.value}")
        return WorldModel((*self.facts, fact), self.rules)

    def add_rule(self, rule: CausalRule) -> WorldModel:
        """Append one causal rule while requiring a unique identity."""
        if any(existing.rule_id == rule.rule_id for existing in self.rules):
            raise FoundationError(f"causal rule already exists: {rule.rule_id.value}")
        return WorldModel(self.facts, (*self.rules, rule))

    def infer(self) -> WorldModel:
        """Apply all currently satisfied rules exactly once in stable order."""
        model = self
        state = model.state()
        known_effects = {
            (fact.subject.value, fact.predicate.value, fact.value.to_payload()["value"])
            for fact in model.facts
        }
        for rule in sorted(model.rules, key=lambda item: item.rule_id.value):
            if not all(condition.matches(state) for condition in rule.conditions):
                continue
            effect_key = (
                rule.effect_subject.value,
                rule.effect_predicate.value,
                rule.effect_value.to_payload()["value"],
            )
            if effect_key in known_effects:
                continue
            derived_ids = tuple(
                state[(condition.subject.value, condition.predicate.value)].fact_id.value
                for condition in rule.conditions
            )
            inferred = WorldFact.create(
                fact_id=f"inferred-{rule.rule_id.value}-{len(model.facts)}",
                subject=rule.effect_subject.value,
                predicate=rule.effect_predicate.value,
                value=rule.effect_value,
                status=FactStatus.INFERRED,
                confidence=rule.confidence,
                evidence_digests=(rule.digest(),),
                derived_from=derived_ids,
            )
            model = model.observe(inferred)
            state = model.state()
            known_effects.add(effect_key)
        return model

    def predict(self) -> tuple[WorldFact, ...]:
        """Return rule effects as predictions without mutating the model."""
        state = self.state()
        predictions: list[WorldFact] = []
        for rule in sorted(self.rules, key=lambda item: item.rule_id.value):
            if all(condition.matches(state) for condition in rule.conditions):
                predictions.append(
                    WorldFact.create(
                        fact_id=f"prediction-{rule.rule_id.value}",
                        subject=rule.effect_subject.value,
                        predicate=rule.effect_predicate.value,
                        value=rule.effect_value,
                        status=FactStatus.PREDICTED,
                        confidence=rule.confidence,
                        evidence_digests=(rule.digest(),),
                        derived_from=tuple(
                            state[
                                (condition.subject.value, condition.predicate.value)
                            ].fact_id.value
                            for condition in rule.conditions
                        ),
                    )
                )
        return tuple(predictions)

    def counterfactual(self, assumptions: Iterable[WorldFact]) -> WorldModel:
        """Evaluate hypothetical assumptions in an isolated model branch."""
        model = self
        for assumption in assumptions:
            if assumption.status is not FactStatus.HYPOTHETICAL:
                raise FoundationError("counterfactual assumptions must be hypothetical")
            model = model.observe(assumption)
        return model.infer()

    def to_payload(self) -> JsonObject:
        """Return a canonical world-model payload."""
        facts: JsonArray = [
            fact.to_payload()
            for fact in sorted(
                self.facts,
                key=lambda candidate: candidate.fact_id.value,
            )
        ]
        rules: JsonArray = [
            rule.to_payload()
            for rule in sorted(
                self.rules,
                key=lambda candidate: candidate.rule_id.value,
            )
        ]
        counts: dict[str, JsonValue] = {
            status.value: sum(1 for fact in self.facts if fact.status is status)
            for status in FactStatus
        }
        return {
            "fact_count": len(self.facts),
            "rule_count": len(self.rules),
            "status_counts": counts,
            "facts": facts,
            "rules": rules,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic world-model identity."""
        return DigestRecord.from_payload(self.to_payload())
