"""Evidence-bound confidence calibration and decision-threshold records."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


@dataclass(frozen=True, slots=True)
class CalibrationObservation:
    """One probability forecast paired with an independently observed outcome."""

    observation_id: CanonicalKey
    capability_id: CanonicalKey
    predicted_probability: float
    observed: bool
    evidence_digest: DigestRecord
    context: str

    @classmethod
    def create(
        cls,
        *,
        observation_id: str,
        capability_id: str,
        predicted_probability: float,
        observed: bool,
        evidence_digest: DigestRecord,
        context: str,
    ) -> CalibrationObservation:
        """Create a calibration observation without altering the forecast."""
        if not 0.0 <= predicted_probability <= 1.0:
            raise FoundationError("predicted probability must be between 0 and 1")
        evidence_digest.require_algorithm("sha256")
        return cls(
            observation_id=CanonicalKey.from_text(
                observation_id,
                field_name="observation_id",
            ),
            capability_id=CanonicalKey.from_text(
                capability_id,
                field_name="capability_id",
            ),
            predicted_probability=predicted_probability,
            observed=observed,
            evidence_digest=evidence_digest,
            context=require_text(context, field_name="context"),
        )

    def squared_error(self) -> float:
        """Return the Brier-score contribution for this forecast."""
        outcome = 1.0 if self.observed else 0.0
        return round((self.predicted_probability - outcome) ** 2, 12)

    def to_payload(self) -> JsonObject:
        """Return a canonical forecast/outcome payload."""
        return {
            "observation_id": self.observation_id.value,
            "capability_id": self.capability_id.value,
            "predicted_probability": self.predicted_probability,
            "observed": self.observed,
            "evidence_digest": {
                "algorithm": self.evidence_digest.algorithm,
                "value": self.evidence_digest.value,
            },
            "context": self.context,
            "squared_error": self.squared_error(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic observation identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class CalibrationBin:
    """One fixed-width confidence bin used by a calibration report."""

    lower_bound: float
    upper_bound: float
    count: int
    mean_prediction: float
    observed_frequency: float
    absolute_gap: float

    def to_payload(self) -> JsonObject:
        """Return a canonical bin payload."""
        return {
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "count": self.count,
            "mean_prediction": self.mean_prediction,
            "observed_frequency": self.observed_frequency,
            "absolute_gap": self.absolute_gap,
        }


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    """Deterministic calibration metrics for one capability or the complete ledger."""

    observation_count: int
    brier_score: float
    expected_calibration_error: float
    bins: tuple[CalibrationBin, ...]

    def __post_init__(self) -> None:
        """Require internally consistent metric ranges."""
        if self.observation_count < 0:
            raise FoundationError("calibration observation count must not be negative")
        if not 0.0 <= self.brier_score <= 1.0:
            raise FoundationError("calibration Brier score must be between 0 and 1")
        if not 0.0 <= self.expected_calibration_error <= 1.0:
            raise FoundationError("calibration error must be between 0 and 1")
        if sum(item.count for item in self.bins) != self.observation_count:
            raise FoundationError("calibration bin counts must equal observation count")

    def to_payload(self) -> JsonObject:
        """Return a canonical calibration-report payload."""
        bins: JsonArray = [item.to_payload() for item in self.bins]
        return {
            "observation_count": self.observation_count,
            "brier_score": self.brier_score,
            "expected_calibration_error": self.expected_calibration_error,
            "bins": bins,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic report identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class UncertaintyLedger:
    """Immutable forecast ledger with transparent calibration calculations."""

    observations: tuple[CalibrationObservation, ...] = ()

    def __post_init__(self) -> None:
        """Reject duplicate observation identifiers."""
        identifiers = [item.observation_id.value for item in self.observations]
        if len(identifiers) != len(set(identifiers)):
            raise FoundationError("uncertainty ledger contains duplicate observations")

    @classmethod
    def create(
        cls,
        observations: Iterable[CalibrationObservation] = (),
    ) -> UncertaintyLedger:
        """Create a ledger in stable identifier order."""
        return cls(tuple(sorted(observations, key=lambda item: item.observation_id.value)))

    def record(self, observation: CalibrationObservation) -> UncertaintyLedger:
        """Return a ledger with one unique forecast/outcome pair appended."""
        return UncertaintyLedger.create((*self.observations, observation))

    def for_capability(self, capability_id: str) -> tuple[CalibrationObservation, ...]:
        """Return observations for one canonical capability."""
        requested = CanonicalKey.from_text(capability_id, field_name="capability_id")
        return tuple(
            item for item in self.observations if item.capability_id == requested
        )

    def report(
        self,
        *,
        capability_id: str | None = None,
        bin_count: int = 10,
    ) -> CalibrationReport:
        """Calculate Brier score and fixed-bin expected calibration error."""
        if bin_count < 1 or bin_count > 100:
            raise FoundationError("calibration bin_count must be between 1 and 100")
        selected = (
            self.observations
            if capability_id is None
            else self.for_capability(capability_id)
        )
        if not selected:
            return CalibrationReport(0, 0.0, 0.0, ())
        bins: list[CalibrationBin] = []
        width = 1.0 / bin_count
        weighted_gap = 0.0
        for index in range(bin_count):
            lower = index * width
            upper = (index + 1) * width
            members = tuple(
                item
                for item in selected
                if lower <= item.predicted_probability
                and (
                    item.predicted_probability < upper
                    or index == bin_count - 1
                )
            )
            if not members:
                continue
            mean_prediction = sum(
                item.predicted_probability for item in members
            ) / len(members)
            observed_frequency = sum(1.0 if item.observed else 0.0 for item in members) / len(
                members
            )
            gap = abs(mean_prediction - observed_frequency)
            weighted_gap += gap * len(members)
            bins.append(
                CalibrationBin(
                    lower_bound=round(lower, 12),
                    upper_bound=round(upper, 12),
                    count=len(members),
                    mean_prediction=round(mean_prediction, 12),
                    observed_frequency=round(observed_frequency, 12),
                    absolute_gap=round(gap, 12),
                )
            )
        brier = sum(item.squared_error() for item in selected) / len(selected)
        return CalibrationReport(
            observation_count=len(selected),
            brier_score=round(brier, 12),
            expected_calibration_error=round(weighted_gap / len(selected), 12),
            bins=tuple(bins),
        )

    def to_payload(self) -> JsonObject:
        """Return a canonical uncertainty-ledger payload."""
        observations: JsonArray = [item.to_payload() for item in self.observations]
        return {"observations": observations}

    def digest(self) -> DigestRecord:
        """Return a deterministic ledger identity."""
        return DigestRecord.from_payload(self.to_payload())
