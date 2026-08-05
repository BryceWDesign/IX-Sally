"""Run a small deterministic IX-Sally cognition and governance demonstration."""

from __future__ import annotations

import sys

from ix_sally.cognition import (
    ActionSpec,
    CognitiveValue,
    FactEffect,
    FactPattern,
    FactStatus,
    GoalSpec,
    SallyCognitiveSystem,
    WorldFact,
)
from ix_sally.digest import DigestRecord, stable_json


def main() -> None:
    """Build a bounded plan and bridge it into IX-Sally's proposal control plane."""
    system = SallyCognitiveSystem.create()
    observation = DigestRecord.from_payload(
        {"sensor": "demo", "machine_state": "off"}
    )
    system.observe(
        WorldFact.create(
            fact_id="demo-machine-off",
            subject="machine",
            predicate="state",
            value=CognitiveValue.from_python("off"),
            status=FactStatus.OBSERVED,
            confidence=1.0,
            evidence_digests=(observation,),
        )
    )
    ready = FactPattern.create(
        subject="machine",
        predicate="state",
        value=CognitiveValue.from_python("ready"),
    )
    system.register_action(
        ActionSpec.create(
            action_id="prepare-demo-machine",
            description="Prepare the simulated demonstration machine.",
            preconditions=(
                FactPattern.create(
                    subject="machine",
                    predicate="state",
                    value=CognitiveValue.from_python("off"),
                ),
            ),
            effects=(
                FactEffect.create(
                    subject="machine",
                    predicate="state",
                    value=CognitiveValue.from_python("ready"),
                ),
            ),
            cost=1.0,
            risk=0.05,
        )
    )
    system.register_goal(
        GoalSpec.create(
            goal_id="prepare-demo-machine",
            description="Reach the simulated ready state.",
            desired_state=ready,
            priority=1.0,
            utility=1.0,
            risk_limit=0.2,
            evidence_digests=(observation,),
        )
    )
    decision = system.deliberate(
        task="Prepare the simulated demonstration machine.",
        use_calibration_gate=False,
    )
    bridged = system.bridge_decision(decision, cycle=0)
    sys.stdout.write(f"{stable_json(bridged.to_payload())}\n")


if __name__ == "__main__":
    main()
