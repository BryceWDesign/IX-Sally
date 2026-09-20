"""Assumption tracking, staleness, contradiction, and targeted revalidation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from ix_sally.cognition.reality_coupling import RealityDelta
from ix_sally.foundation import FoundationError, require_text


class AssumptionStatus(StrEnum):
    ACTIVE = "active"
    VALIDATED = "validated"
    REVALIDATION_REQUIRED = "revalidation-required"
    CONTRADICTED = "contradicted"
    QUARANTINED = "quarantined"


@dataclass(frozen=True, slots=True)
class Assumption:
    assumption_id: str
    statement: str
    confidence: float
    impact_if_wrong: float
    evidence_ids: tuple[str, ...] = ()
    age: int = 0
    max_age: int = 100
    status: AssumptionStatus = AssumptionStatus.ACTIVE

    def __post_init__(self) -> None:
        require_text(self.assumption_id, field_name="assumption_id")
        require_text(self.statement, field_name="statement")
        if not 0.0 <= self.confidence <= 1.0:
            raise FoundationError("assumption confidence must be between zero and one")
        if not 0.0 <= self.impact_if_wrong <= 1.0:
            raise FoundationError("assumption impact must be between zero and one")
        if self.age < 0 or self.max_age < 1:
            raise FoundationError("assumption age must be non-negative and max_age positive")

    @property
    def stale(self) -> bool:
        return self.age >= self.max_age

    @property
    def risk(self) -> float:
        return round((1.0 - self.confidence) * self.impact_if_wrong, 12)


@dataclass(frozen=True, slots=True)
class AssumptionDiagnosis:
    assumption_ids: tuple[str, ...]
    reason: str
    revalidation_required: bool


class AssumptionLedger:
    """Mutable ledger with immutable assumption records."""

    def __init__(self) -> None:
        self._items: dict[str, Assumption] = {}

    def register(self, assumption: Assumption) -> None:
        if assumption.assumption_id in self._items:
            raise FoundationError(f"duplicate assumption: {assumption.assumption_id}")
        self._items[assumption.assumption_id] = assumption

    def get(self, assumption_id: str) -> Assumption:
        item = self._items.get(assumption_id)
        if item is None:
            raise FoundationError(f"unknown assumption: {assumption_id}")
        return item

    def age(self, steps: int = 1) -> None:
        if steps < 0:
            raise FoundationError("assumption aging steps must not be negative")
        for key, item in tuple(self._items.items()):
            aged = replace(item, age=item.age + steps)
            if aged.stale and aged.status in {AssumptionStatus.ACTIVE, AssumptionStatus.VALIDATED}:
                aged = replace(aged, status=AssumptionStatus.REVALIDATION_REQUIRED)
            self._items[key] = aged

    def diagnose(self, delta: RealityDelta) -> AssumptionDiagnosis:
        candidates = tuple(
            self._items[identifier]
            for identifier in delta.dependency_ids
            if identifier in self._items
        )
        if not candidates:
            return AssumptionDiagnosis((), "prediction has no registered assumptions", False)
        ranked = sorted(
            candidates,
            key=lambda item: (item.impact_if_wrong * delta.surprise, item.assumption_id),
            reverse=True,
        )
        suspect_ids = tuple(item.assumption_id for item in ranked if item.impact_if_wrong >= 0.35)
        required = delta.strong_contradiction or any(item.stale for item in candidates)
        if required:
            for identifier in suspect_ids:
                item = self._items[identifier]
                status = (
                    AssumptionStatus.CONTRADICTED
                    if delta.strong_contradiction
                    else AssumptionStatus.REVALIDATION_REQUIRED
                )
                self._items[identifier] = replace(item, status=status)
        return AssumptionDiagnosis(
            assumption_ids=suspect_ids,
            reason=(
                "strong reliable prediction contradiction implicates dependent assumptions"
                if delta.strong_contradiction
                else "dependent assumptions should be rechecked before stronger commitment"
            ),
            revalidation_required=required,
        )

    def validate(self, assumption_id: str, *, evidence_id: str) -> None:
        require_text(evidence_id, field_name="evidence_id")
        item = self.get(assumption_id)
        evidence = tuple(dict.fromkeys((*item.evidence_ids, evidence_id)))
        self._items[assumption_id] = replace(
            item,
            status=AssumptionStatus.VALIDATED,
            age=0,
            evidence_ids=evidence,
        )

    def quarantine(self, assumption_id: str) -> None:
        item = self.get(assumption_id)
        self._items[assumption_id] = replace(item, status=AssumptionStatus.QUARANTINED)

    def items(self) -> tuple[Assumption, ...]:
        return tuple(self._items[key] for key in sorted(self._items))
