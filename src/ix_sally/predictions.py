"""IX-Oracle prediction packets for forecast and reality-delta discipline."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifact, AgentArtifactKind
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_optional_text, require_text


class PredictionStatus(StrEnum):
    """Status assigned to an IX-Oracle prediction."""

    PENDING_OUTCOME = "pending_outcome"
    MATCHED = "matched"
    PARTIAL = "partial"
    MISSED = "missed"
    UNTESTABLE = "untestable"


@dataclass(frozen=True, slots=True)
class OraclePrediction:
    """A prediction made before action so outcome correction can be measured."""

    prediction_id: CanonicalKey
    cycle: int
    target_digest: DigestRecord
    expected_outcome: str
    rationale: str
    status: PredictionStatus = PredictionStatus.PENDING_OUTCOME
    observed_outcome: str | None = None
    delta_note: str | None = None

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        target_digest: DigestRecord,
        expected_outcome: str,
        rationale: str,
        status: PredictionStatus = PredictionStatus.PENDING_OUTCOME,
        observed_outcome: str | None = None,
        delta_note: str | None = None,
        prediction_id: CanonicalKey | None = None,
    ) -> OraclePrediction:
        """Create a normalized IX-Oracle prediction."""
        if cycle < 0:
            raise FoundationError("prediction cycle must not be negative")

        target_digest.require_algorithm("sha256")
        normalized_expected = require_text(expected_outcome, field_name="expected_outcome")
        normalized_rationale = require_text(rationale, field_name="rationale")
        normalized_observed = require_optional_text(
            observed_outcome,
            field_name="observed_outcome",
        )
        normalized_delta = require_optional_text(delta_note, field_name="delta_note")

        if status is not PredictionStatus.PENDING_OUTCOME and normalized_observed is None:
            raise FoundationError("resolved predictions require an observed outcome")

        if (
            status in {PredictionStatus.PARTIAL, PredictionStatus.MISSED}
            and normalized_delta is None
        ):
            raise FoundationError("partial or missed predictions require a delta note")

        return cls(
            prediction_id=prediction_id
            or CanonicalKey.from_text(
                f"ix-oracle-{cycle}-{normalized_expected}",
                field_name="prediction_id",
            ),
            cycle=cycle,
            target_digest=target_digest,
            expected_outcome=normalized_expected,
            rationale=normalized_rationale,
            status=status,
            observed_outcome=normalized_observed,
            delta_note=normalized_delta,
        )

    def is_resolved(self) -> bool:
        """Return whether this prediction has been compared to an outcome."""
        return self.status is not PredictionStatus.PENDING_OUTCOME

    def needs_memory_review(self) -> bool:
        """Return whether reality-delta should be reviewed before learning."""
        return self.status in {PredictionStatus.PARTIAL, PredictionStatus.MISSED}

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible prediction representation."""
        return {
            "prediction_id": self.prediction_id.value,
            "cycle": self.cycle,
            "target_digest": {
                "algorithm": self.target_digest.algorithm,
                "value": self.target_digest.value,
            },
            "expected_outcome": self.expected_outcome,
            "rationale": self.rationale,
            "status": self.status.value,
            "observed_outcome": self.observed_outcome,
            "delta_note": self.delta_note,
            "is_resolved": self.is_resolved(),
            "needs_memory_review": self.needs_memory_review(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this prediction."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class OraclePredictionPacket:
    """Structured IX-Oracle packet containing forecast records for a target."""

    packet_id: CanonicalKey
    cycle: int
    forecast_summary: str
    predictions: tuple[OraclePrediction, ...]

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        forecast_summary: str,
        predictions: Iterable[OraclePrediction],
        packet_id: CanonicalKey | None = None,
    ) -> OraclePredictionPacket:
        """Create a normalized IX-Oracle prediction packet."""
        if cycle < 0:
            raise FoundationError("prediction packet cycle must not be negative")

        normalized_summary = require_text(forecast_summary, field_name="forecast_summary")
        normalized_predictions = tuple(predictions)

        if not normalized_predictions:
            raise FoundationError("prediction packet requires at least one prediction")

        for prediction in normalized_predictions:
            if prediction.cycle != cycle:
                raise FoundationError("predictions must match packet cycle")

        return cls(
            packet_id=packet_id
            or CanonicalKey.from_text(
                f"ix-oracle-{cycle}-{normalized_summary}",
                field_name="packet_id",
            ),
            cycle=cycle,
            forecast_summary=normalized_summary,
            predictions=normalized_predictions,
        )

    def resolved_count(self) -> int:
        """Return the number of predictions that have outcome comparisons."""
        return sum(1 for prediction in self.predictions if prediction.is_resolved())

    def memory_review_count(self) -> int:
        """Return the number of predictions with reality-delta needing review."""
        return sum(1 for prediction in self.predictions if prediction.needs_memory_review())

    def to_artifact(self) -> AgentArtifact:
        """Convert this packet into a shared runtime artifact."""
        return AgentArtifact.create(
            cycle=self.cycle,
            role=AgentRole.ORACLE,
            kind=AgentArtifactKind.PREDICTION,
            summary=f"IX-Oracle recorded {len(self.predictions)} prediction(s).",
            referenced_digests=tuple(prediction.digest() for prediction in self.predictions),
            data=self.to_payload(),
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible prediction packet representation."""
        predictions_payload: JsonArray = []
        for prediction in self.predictions:
            predictions_payload.append(prediction.to_payload())

        return {
            "packet_id": self.packet_id.value,
            "cycle": self.cycle,
            "forecast_summary": self.forecast_summary,
            "predictions": predictions_payload,
            "resolved_count": self.resolved_count(),
            "memory_review_count": self.memory_review_count(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this prediction packet."""
        return DigestRecord.from_payload(self.to_payload())
