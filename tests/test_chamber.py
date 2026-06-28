from __future__ import annotations

import pytest

from ix_sally.chamber import ObservationChamberConfig, StopCondition, StopReason
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.doctrine import default_doctrine_catalog
from ix_sally.foundation import FoundationError


def test_observation_chamber_validates_bound_doctrine() -> None:
    contract = AutonomyContract.create(
        goal="Observe a governed agent cycle.",
        mode=AutonomyMode.OBSERVE,
        max_cycles=2,
        doctrine_keys=("output-is-not-evidence", "memory-is-not-truth"),
    )
    chamber = ObservationChamberConfig.create(
        contract=contract,
        doctrine_catalog=default_doctrine_catalog(),
    )

    assert chamber.observer_label == "human-boundary-observer"
    assert chamber.sandbox_required is True
    assert chamber.external_messaging_allowed is False


def test_observation_chamber_rejects_missing_doctrine_binding() -> None:
    contract = AutonomyContract.create(
        goal="Observe a governed agent cycle.",
        mode=AutonomyMode.OBSERVE,
        max_cycles=2,
        doctrine_keys=("missing-doctrine-rule",),
    )

    with pytest.raises(FoundationError, match="unknown doctrine rule"):
        ObservationChamberConfig.create(
            contract=contract,
            doctrine_catalog=default_doctrine_catalog(),
        )


def test_observation_chamber_requires_human_boundary_authority() -> None:
    contract = AutonomyContract.create(
        goal="Observe a governed agent cycle.",
        mode=AutonomyMode.OBSERVE,
        max_cycles=2,
        human_boundary_required=False,
    )

    with pytest.raises(FoundationError, match="requires human boundary authority"):
        ObservationChamberConfig.create(
            contract=contract,
            doctrine_catalog=default_doctrine_catalog(),
        )


def test_observation_chamber_rejects_network_without_external_messaging() -> None:
    contract = AutonomyContract.create(
        goal="Observe a governed agent cycle.",
        mode=AutonomyMode.RESEARCH,
        max_cycles=2,
        network_allowed=True,
    )

    with pytest.raises(FoundationError, match="network access cannot be enabled"):
        ObservationChamberConfig.create(
            contract=contract,
            doctrine_catalog=default_doctrine_catalog(),
            external_messaging_allowed=False,
        )


def test_observation_chamber_cycle_stop_condition() -> None:
    contract = AutonomyContract.create(
        goal="Observe a governed agent cycle.",
        mode=AutonomyMode.OBSERVE,
        max_cycles=2,
    )
    chamber = ObservationChamberConfig.create(
        contract=contract,
        doctrine_catalog=default_doctrine_catalog(),
    )

    assert chamber.stop_for_cycle(0) == StopCondition.continue_run()
    assert chamber.stop_for_cycle(1) == StopCondition.continue_run()

    stop = chamber.stop_for_cycle(2)

    assert stop.should_stop is True
    assert stop.reason is StopReason.MAX_CYCLES_REACHED
    assert stop.detail == "completed_cycles=2 reached max_cycles=2"


def test_stop_for_cycle_rejects_negative_completed_cycles() -> None:
    contract = AutonomyContract.create(
        goal="Observe a governed agent cycle.",
        mode=AutonomyMode.OBSERVE,
        max_cycles=1,
    )
    chamber = ObservationChamberConfig.create(
        contract=contract,
        doctrine_catalog=default_doctrine_catalog(),
    )

    with pytest.raises(FoundationError, match="completed_cycles must not be negative"):
        chamber.stop_for_cycle(-1)


def test_stop_condition_requires_detail_when_stopping() -> None:
    with pytest.raises(FoundationError, match="detail must not be empty"):
        StopCondition.stop(reason=StopReason.HUMAN_TERMINATED, detail="   ")


def test_chamber_digest_changes_when_boundary_changes() -> None:
    contract = AutonomyContract.create(
        goal="Observe a governed agent cycle.",
        mode=AutonomyMode.OBSERVE,
        max_cycles=1,
    )
    first = ObservationChamberConfig.create(
        contract=contract,
        doctrine_catalog=default_doctrine_catalog(),
        sandbox_required=True,
    )
    second = ObservationChamberConfig.create(
        contract=contract,
        doctrine_catalog=default_doctrine_catalog(),
        sandbox_required=False,
    )

    assert first.digest().value != second.digest().value
