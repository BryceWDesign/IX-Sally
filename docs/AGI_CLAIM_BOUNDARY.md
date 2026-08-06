# AGI Claim Boundary

## What this repository establishes

IX-Sally implements and tests a coherent experimental cognitive architecture
with typed execution, grounded primitives, bounded attention, active memory,
world modeling, causal inference, prediction, planning, goal selection,
uncertainty calibration, curricula, held-out transfer records, metacognition,
regression-aware adaptation, replayable episodes, persistence, and governance.

The repository also integrates those functions with a mature human-authority
control plane rather than allowing cognition to grant itself execution rights.

## What this repository does not establish

Completion of the software architecture does not establish artificial general
intelligence. The repository does not prove:

- open-world general intelligence;
- human-level intelligence;
- autonomous scientific discovery;
- robust embodiment;
- broad real-world transfer;
- safe self-improvement;
- production safety;
- legal or regulatory compliance;
- certification of any kind.

No external foundation-model weights, training corpus, sensor stream, robotics
stack, or proprietary benchmark dataset is bundled. That is not a missing file
inside the implementation; it is an explicit system boundary.

## Why the built-in evaluation is not an AGI test

The built-in suite is deterministic and local. It verifies that implemented
mechanisms behave as specified. It does not measure the breadth, efficiency,
novelty, autonomy, or environmental robustness required for an AGI claim.

The evaluation report therefore fixes:

```text
classification = experimental-cognitive-architecture
agi_certified = false
```

Attempting to construct a report with `agi_certified = true` raises an error.

## Evidence required before stronger claims

Any future stronger claim would require external, reproducible evidence such as:

- broad unfamiliar-task benchmarks;
- held-out task families that were not used during implementation;
- ablation studies;
- baseline comparisons;
- long-horizon retention studies;
- adversarial evaluation;
- independent replication;
- measured resource efficiency;
- real-world or high-fidelity environment interaction;
- documented failure cases and confidence calibration.

Until such evidence exists, the accurate description is:

> IX-Sally is a governed experimental cognitive runtime and research
> architecture. It is not a demonstrated AGI.
