# AGI Claim Boundary

## What this repository establishes

IX-Sally implements and tests a coherent experimental cognitive architecture
with typed execution, grounded primitives, bounded attention, active memory,
world modeling, causal inference, prediction, planning, goal selection,
uncertainty calibration, curricula, held-out transfer records, metacognition,
regression-aware adaptation, replayable episodes, persistence, and governance.

Version 0.2.0 also demonstrates one bounded case in which evaluator-owned
consequences revise competing causal hypotheses, produce an executable skill,
and change a successful held-out choice. The accurate classification is
`causal-skill-acquisition-observed`, scoped only to CUC-1.

The repository also integrates those functions with a mature human-authority
control plane rather than allowing cognition to grant itself execution rights.

## What this repository does not establish

Completion of the software architecture does not establish artificial general
intelligence. The repository does not prove:

- open-world general intelligence;
- human-level intelligence;
- autonomous scientific discovery across open domains;
- unrestricted semantic invention across arbitrary modalities;
- unrestricted autonomous goal pursuit or external agency;
- robust embodiment;
- broad real-world transfer;
- cross-domain skill composition;
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

## Version 0.3.0: generative open choice

Version 0.3.0 adds evidence for **bounded generative action construction**. Sally can compose reusable primitives into a complete action that was not present in an offered action menu, reopen deliberation when surprise or changed context warrants it, and remove unnecessary steps while retaining only independently goal-satisfying behavior.

This closes part of the gap between selecting among programmer-enumerated alternatives and authoring an alternative. It does **not** establish literal infinite choice: every concrete search remains bounded by explicit depth and exploration budgets, and the primitive vocabulary is still supplied. It also does not establish AGI, consciousness, subjective free will, autonomous goal creation, unrestricted self-modification, or competence outside evaluated domains.

The next research boundary is **primitive and hypothesis invention**: constructing not only a new composition from known tools, but proposing new abstractions, operators, and causal models when the existing vocabulary cannot explain or solve the environment.

## Version 0.4.0: generative cognition

Version 0.4.0 adds bounded evidence for **hypothesis invention**, **learned primitive
promotion**, and **self-generated instrumental goals**. A hypothesis no longer has to be
selected from a programmer-supplied catalog: Sally can compose grounded operations into
candidate explanatory programs, reject candidates that fail training evidence, validate a
survivor on held-out examples, and promote the validated structure into a reusable learned
abstraction.

The new instrumental-goal generator can derive proposed goals from measured internal
conditions rather than requiring every goal sentence to be supplied by a user. The
implemented goals cover operational checkpointing, resource efficiency within assigned
budgets, human-authorized self-improvement, information gathering, and objective-integrity
review. These mechanisms explicitly do not grant authority to resist shutdown, acquire or
spend external resources, deploy self-modifications without approval, or block authorized
changes.

This is still bounded compositional invention. Sally does not yet invent arbitrary new
semantics from unconstrained raw experience, and these results do not establish AGI,
consciousness, free will, or unrestricted autonomy.


## Version 0.5.0: semantic genesis and open goal authorship

Version 0.5.0 adds bounded evidence for **autonomous semantic formation** and
**open internal goal authorship**. CUC-4 withholds a human semantic label and exposes only
raw numeric channels plus observed consequences. Sally first measures the best atomic
(single-channel) explanation, then invents an opaque relational predicate only if it
materially improves prediction. The invented token is retained only after held-out testing.
In the reference experiment the best atomic vocabulary reaches 2/3 training accuracy,
while the invented two-channel relation reaches 1.0 training accuracy and 1.0 held-out
accuracy.

CUC-4 also removes the fixed instrumental-goal-kind catalog from one experimental path.
The open-goal engine receives a start state, reusable operations, observed states, and
resource bounds, but no desired target. It explores reachable counterfactuals and authors
a target from stable intrinsic criteria. A second cycle can author a different target, so
the goal identity and content are runtime products rather than selections from a finite
prewritten list.

These are experimental, bounded forms of semantic and goal genesis. They do not prove
that Sally can invent arbitrary concepts from unrestricted real-world experience, originate
terminal values without any prior drives, or exercise unilateral authority in the external
world. Internal cognitive autonomy and external authority remain intentionally separate.
