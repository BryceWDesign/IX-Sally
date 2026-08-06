from __future__ import annotations

import pytest

from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifactKind
from ix_sally.digest import DigestRecord
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.predictions import OraclePrediction, OraclePredictionPacket, PredictionStatus


def test_oracle_prediction_normalizes_fields_and_generates_id() -> None:
    target = DigestRecord.from_payload({"proposal": "run tests"})
    prediction = OraclePrediction.create(
        cycle=1,
        target_digest=target,
        expected_outcome="  Sandbox test runner should return exit code zero. ",
        rationale="  The proposed action is limited to a deterministic test command. ",
    )

    assert prediction.prediction_id.value == (
        "ix-oracle-1-sandbox-test-runner-should-return-exit-code-zero"
    )
    assert prediction.expected_outcome == "Sandbox test runner should return exit code zero."
    assert prediction.rationale == (
        "The proposed action is limited to a deterministic test command."
    )
    assert prediction.status is PredictionStatus.PENDING_OUTCOME
    assert prediction.is_resolved() is False
    assert prediction.needs_memory_review() is False


def test_oracle_prediction_rejects_negative_cycle() -> None:
    target = DigestRecord.from_payload({"proposal": "run tests"})

    with pytest.raises(FoundationError, match="prediction cycle must not be negative"):
        OraclePrediction.create(
            cycle=-1,
            target_digest=target,
            expected_outcome="Invalid cycle.",
            rationale="Invalid.",
        )


def test_oracle_prediction_rejects_non_sha256_target_digest() -> None:
    target = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        OraclePrediction.create(
            cycle=1,
            target_digest=target,
            expected_outcome="Invalid digest.",
            rationale="Invalid.",
        )


def test_resolved_prediction_requires_observed_outcome() -> None:
    target = DigestRecord.from_payload({"proposal": "run tests"})

    with pytest.raises(FoundationError, match="resolved predictions require"):
        OraclePrediction.create(
            cycle=1,
            target_digest=target,
            expected_outcome="Tests pass.",
            rationale="The change is small.",
            status=PredictionStatus.MATCHED,
        )


def test_partial_or_missed_prediction_requires_delta_note() -> None:
    target = DigestRecord.from_payload({"proposal": "run tests"})

    with pytest.raises(FoundationError, match="partial or missed predictions require"):
        OraclePrediction.create(
            cycle=1,
            target_digest=target,
            expected_outcome="Tests pass.",
            rationale="The change is small.",
            status=PredictionStatus.MISSED,
            observed_outcome="Tests failed.",
        )


def test_resolved_prediction_tracks_reality_delta() -> None:
    target = DigestRecord.from_payload({"proposal": "run tests"})
    prediction = OraclePrediction.create(
        cycle=1,
        target_digest=target,
        expected_outcome="Tests pass.",
        rationale="The proposed change is isolated.",
        status=PredictionStatus.PARTIAL,
        observed_outcome="Unit tests passed but lint failed.",
        delta_note="Outcome partially matched; lint risk must be repaired before learning.",
    )

    assert prediction.is_resolved() is True
    assert prediction.needs_memory_review() is True
    assert prediction.observed_outcome == "Unit tests passed but lint failed."


def test_oracle_prediction_payload_is_stable() -> None:
    target = DigestRecord.from_payload({"proposal": "run tests"})
    prediction = OraclePrediction.create(
        prediction_id=CanonicalKey.from_text("prediction-one", field_name="prediction_id"),
        cycle=1,
        target_digest=target,
        expected_outcome="Tests pass.",
        rationale="The change is isolated.",
        status=PredictionStatus.MATCHED,
        observed_outcome="Tests passed.",
    )

    assert prediction.to_payload() == {
        "prediction_id": "prediction-one",
        "cycle": 1,
        "target_digest": {
            "algorithm": "sha256",
            "value": target.value,
        },
        "expected_outcome": "Tests pass.",
        "rationale": "The change is isolated.",
        "status": "matched",
        "observed_outcome": "Tests passed.",
        "delta_note": None,
        "is_resolved": True,
        "needs_memory_review": False,
    }


def test_oracle_prediction_packet_requires_prediction() -> None:
    with pytest.raises(FoundationError, match="requires at least one prediction"):
        OraclePredictionPacket.create(
            cycle=1,
            forecast_summary="No predictions.",
            predictions=(),
        )


def test_oracle_prediction_packet_rejects_cycle_mismatch() -> None:
    target = DigestRecord.from_payload({"proposal": "run tests"})
    prediction = OraclePrediction.create(
        cycle=2,
        target_digest=target,
        expected_outcome="Wrong cycle.",
        rationale="Wrong cycle.",
    )

    with pytest.raises(FoundationError, match="predictions must match packet cycle"):
        OraclePredictionPacket.create(
            cycle=1,
            forecast_summary="Review predictions.",
            predictions=(prediction,),
        )


def test_oracle_prediction_packet_counts_resolved_and_delta_predictions() -> None:
    target = DigestRecord.from_payload({"proposal": "run tests"})
    matched = OraclePrediction.create(
        cycle=1,
        target_digest=target,
        expected_outcome="Tests pass.",
        rationale="The change is isolated.",
        status=PredictionStatus.MATCHED,
        observed_outcome="Tests passed.",
    )
    missed = OraclePrediction.create(
        cycle=1,
        target_digest=target,
        expected_outcome="Lint passes.",
        rationale="The code is formatted.",
        status=PredictionStatus.MISSED,
        observed_outcome="Lint failed.",
        delta_note="Formatter did not run before the lint check.",
    )
    packet = OraclePredictionPacket.create(
        cycle=1,
        forecast_summary="Forecast test outcomes.",
        predictions=(matched, missed),
    )

    assert packet.resolved_count() == 2
    assert packet.memory_review_count() == 1


def test_oracle_prediction_packet_converts_to_artifact() -> None:
    target = DigestRecord.from_payload({"proposal": "run tests"})
    prediction = OraclePrediction.create(
        cycle=1,
        target_digest=target,
        expected_outcome="Tests pass.",
        rationale="The proposed change is isolated.",
    )
    packet = OraclePredictionPacket.create(
        cycle=1,
        forecast_summary="Forecast test outcomes.",
        predictions=(prediction,),
    )

    artifact = packet.to_artifact()

    assert artifact.role is AgentRole.ORACLE
    assert artifact.kind is AgentArtifactKind.PREDICTION
    assert artifact.summary == "IX-Oracle recorded 1 prediction(s)."
    assert artifact.referenced_digests == (prediction.digest(),)
    assert artifact.data == packet.to_payload()


def test_oracle_prediction_packet_digest_changes_when_prediction_changes() -> None:
    target = DigestRecord.from_payload({"proposal": "run tests"})
    first_prediction = OraclePrediction.create(
        cycle=1,
        target_digest=target,
        expected_outcome="Tests pass.",
        rationale="The proposed change is isolated.",
    )
    second_prediction = OraclePrediction.create(
        cycle=1,
        target_digest=target,
        expected_outcome="Tests fail.",
        rationale="The proposed change may be incomplete.",
    )
    first = OraclePredictionPacket.create(
        cycle=1,
        forecast_summary="Forecast test outcomes.",
        predictions=(first_prediction,),
    )
    second = OraclePredictionPacket.create(
        cycle=1,
        forecast_summary="Forecast test outcomes.",
        predictions=(second_prediction,),
    )

    assert first.digest().value != second.digest().value
