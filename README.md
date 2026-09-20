# IX-Sally

IX-Sally is a source-available, evaluation-only governed experimental cognitive
runtime. It combines a deterministic human-authority control plane with typed
IX language execution, bounded memory, world modeling, planning, learning,
metacognition, persistence, and evidence-linked proposal generation.

The controlling rule is:

> **AI proposes. Humans decide. Evidence governs what may proceed.**

IX-Sally is not a demonstrated AGI, autonomous deployment platform,
certification authority, or substitute for independent engineering and human
judgment.


## v0.7.0 lifelong generalization and representational freedom

IX-Sally v0.7.0 targets the remaining gap between having individual cognitive mechanisms and
becoming measurably better at learning because of prior experience. CUC-6 adds a bounded
compositional representation language, persistent online meta-learning, active lifelong
knowledge maintenance, surface-independent relational transfer, raw-text outcome grounding,
and multi-goal portfolio coherence. These mechanisms are integrated into
`SallyCognitiveSystem` and persist through canonical snapshot/restore where stateful.

The strongest CUC-6 representation task cannot be perfectly expressed by the prior one-step
feature language. The best shallow representation reaches 0.8125 training accuracy. Sally
synthesizes the multi-operation expression `((x0*x1)+x2)`, reaches 1.0 training accuracy, and
retains 1.0 accuracy on held-out values outside the training range.

CUC-6 also runs twelve sealed numeric worlds. During the first two worlds Sally evaluates both
available learning strategies. Its online meta-profile then changes later learning: the
remaining worlds select one strategy from accumulated structural experience instead of
re-running both strategy families, while retaining 1.0 held-out accuracy. The challenge IDs
and channel orderings change; strategy selection is based on measured task fingerprints rather
than a hard-coded world-type switch.

Additional v0.7 mechanisms include contextual concept splitting when a formerly useful rule
becomes systematically wrong in one regime, structural analogy that transfers a learned
topological role from an industrial-control graph to a software-rendering graph despite
different entity and relation names, empirical token grounding from raw text/outcome pairs,
and dependency-aware attention allocation across multiple goals with premise collapse and
goal abandonment. A 64-generation bounded maintenance/checkpoint exercise verifies that the
meta-learning profile and lifelong store survive exact snapshot/restore.

These are bounded research results. v0.7 does not establish AGI, consciousness, unrestricted
self-modification, general vision/audio grounding, unlimited open-world agency, or independent
replication. External consequential action remains governed by the inherited human-authority
control plane. See `docs/CUC6_LIFELONG_GENERALIZATION.md` and `VALIDATION_REPORT.md`.

Run the experiment:

```text
python -m ix_sally --cuc6-experiment
```


## v0.6.0 recursive cognitive bootstrapping

IX-Sally v0.6.0 integrates the major bounded mechanisms that remained after v0.5.0 into a
single recursive research path instead of presenting them as disconnected feature claims.
CUC-5 demonstrates a closed cycle where an atomic representation fails, Sally invents and
validates a new representation, promotes the discovery into a reusable opaque semantic
primitive, persists it, authors an internal goal afterward, constructs an action for that
goal, validates the procedure into a reusable tool, detects a structured high-confidence
failure, and invents a second, different representation.

The release also adds long-horizon replanning, structural cross-domain transfer,
self-directed curriculum selection, persistent lifelong knowledge and ontology
restructuring, intervention-aware causal discovery, numeric raw-signal grounding, active
perception, counterfactual imagination, self-diagnosis, governed measured self-improvement,
goal conflict resolution and abandonment, unknown-unknown detection, adaptive search
budgeting, meta-learning, procedural unfamiliar-world tests, and a nonce-bound blind
evaluator interface for challenge sets supplied by third parties.

These are bounded experimental mechanisms, not an AGI certification. Raw perception remains
limited to numeric streams, every concrete search is finite, and genuinely independent
evaluation still requires an external evaluator. External consequential action and adoption
of self-improvement proposals remain under the existing human-authority control plane. See
`docs/CUC5_RECURSIVE_COGNITION.md`, `docs/CUC5_VALIDATION_REPORT.md`, and
`VALIDATION_REPORT.md`.

Run the integrated experiment:

```text
python -m ix_sally --cuc5-experiment
```

## v0.5.0 semantic genesis and open goal authorship

IX-Sally now includes CUC-4, which adds two bounded research capabilities that were not
present in v0.4.0. First, Sally can create an opaque latent semantic distinction directly
from unexplained relations among raw numeric channels when every single-channel
explanation is materially worse. The concept receives no human semantic label, must beat
the existing atomic vocabulary, and must survive held-out reality testing. Second, Sally
can author internal sandbox goals without receiving a target value or selecting from a
fixed goal-kind catalog. A bounded counterfactual search generates reachable possibilities
and Sally selects a target using intrinsic novelty, information value, competence expansion,
simplicity, reversibility, and risk. Generated goals do not grant external authority. See
`docs/CUC4_SEMANTIC_GOAL_GENESIS.md` and `docs/CUC4_VALIDATION_REPORT.md`.


## v0.4.0 generative cognition

IX-Sally now includes CUC-3, which moves beyond action composition into bounded
**hypothesis invention** and **primitive invention**. Sally can synthesize an explanatory
program directly from observed input/output evidence without receiving a hypothesis
catalog, test that program on held-out evidence, and promote a validated program into a
new reusable learned abstraction. Sally can also derive proposed instrumental goals from
measured internal conditions such as capability weakness, uncertainty, continuity risk,
resource pressure, and integrity anomalies. Self-improvement remains proposal-only until
human authorization; continuity never implies resistance to shutdown, resource goals do
not authorize external acquisition or spending, and objective-integrity goals do not block
authorized changes. See `docs/CUC3_GENERATIVE_COGNITION.md`.

## v0.3.0 generative open choice

IX-Sally now includes a bounded generative choice subsystem that can construct complete actions from reusable primitives rather than selecting only from a pre-enumerated menu. CUC-2 demonstrates a case where all four offered single-step actions fail and Sally composes a new multi-step action that reaches the goal. Surprise, context shift, conflict, or a newly valuable alternative can reopen deliberation even when a learned skill exists. A minimal-sufficiency pass can also remove unnecessary steps while retaining only solutions that still pass an independent goal test. See `docs/CUC2_OPEN_CHOICE.md`.

## Version 0.2.0: Choice Under Consequence

Version 0.2.0 adds the first closed-loop acquired-capability experiment,
**Choice Under Consequence 1 (CUC-1)**. Unlike the repository's mechanism
checks, CUC-1 begins with uncertainty over a hidden causal transformation and
requires measured interaction to change later behavior.

The experiment provides:

- an evaluator-owned causal rule absent from agent-visible observations;
- four competing causal hypotheses with an initially uniform prior;
- transparent action scoring across expected success, information gain,
  novelty, reversibility, cost, and risk;
- evaluator-generated consequences after every intervention;
- Bayesian belief revision from success and failure;
- compilation of a supported hypothesis into an executable skill;
- transfer of that skill to a held-out cue;
- a frozen pre-learning counterfactual on the same held-out observation;
- random and fixed-action baselines;
- content-addressed choices, consequences, state transitions, and rule commitment;
- explicit leakage checks and post-run rule reveal for reproducibility.

The default observed run begins with four equally likely transformations. Three
failed interventions eliminate inconsistent hypotheses. The surviving rule is
compiled into a skill, succeeds on the fourth training intervention, and then
succeeds on a held-out cue. On that same held-out observation, the frozen
pre-learning agent selects `north`; the learned agent selects `east`.

The bounded classification is:

```text
causal-skill-acquisition-observed
```

This is not an AGI claim. The task family contains four rotation hypotheses,
transfer remains within that family, and no independent replication has
occurred.

Run the experiment:

```text
python -m ix_sally --cuc1-experiment
```

Select another deterministic evaluator seed:

```text
python -m ix_sally --cuc1-experiment --cuc1-seed 11
```

The command exits successfully only when its strict acquired-competence claim
is supported. See `docs/CUC1_EXPERIMENT.md` for its protocol and falsification
criteria.

## What is delivered

The repository contains two integrated architectural layers.

### Governed control plane

The inherited IX-Sally control plane provides:

- deterministic canonical records and SHA-256 digest links;
- doctrine, claims, jurisdiction, contracts, and bounded run state;
- proposal intake and proposal gateways;
- evidence records, support findings, and evidence processing;
- stage readiness, stage gates, orchestration, and advance receipts;
- execution planning, queues, dispatch, and Forge result processing;
- human-review handoffs, dockets, packets, bundles, and decisions;
- clearance, resume certification, reentry, audit, and complete reentry;
- closeout reports, ledgers, coordination records, and export packets;
- explicit separation between capability, evidence, permission, and authority.

### Experimental cognitive runtime

The cognitive runtime adds:

- complete IX lexical, syntactic, semantic, and type analysis;
- exact typed cognitive scalar values;
- deterministic bytecode compilation;
- a bounded step-limited virtual machine;
- immutable execution status, failure, output, memory, and trace receipts;
- atomic VM memory commitment after a clean halt;
- grounded closed-catalog primitives without dynamic Python callbacks;
- a bounded typed attention workspace;
- working, episodic, semantic, and procedural memory;
- explicit pending, verified, stale, contradicted, and quarantined status;
- replayable digest-linked cognitive episodes;
- observed, inferred, predicted, hypothetical, and contradicted world facts;
- evidence-bound causal inference, prediction, and counterfactual simulation;
- dependency-aware goals and bounded deterministic planning;
- exact preconditions, effects, cost, risk, and authority metadata;
- calibrated uncertainty, Brier score, and calibration-error reporting;
- training, validation, and held-out curriculum splits;
- evidence-bound learning, retention, and transfer records;
- an evidence-limited self model and regression-aware adaptation proposals;
- a functional ninefold cognitive cycle using IX-Sally's canonical roles;
- complete canonical snapshots, exact restoration, backup, and recovery;
- an explicit bridge from cognitive plans into the existing proposal path;
- human-authority and risk gates before consequential action may proceed.
- a sealed causal-learning experiment where consequence changes future choice.
- bounded latent semantic genesis from raw relational structure with held-out validation.
- runtime authorship of novel internal sandbox goal targets without a fixed goal-kind catalog.
- bounded representation invention that can create non-atomic feature spaces when raw channels fail.
- validated semantic promotion and persistent lifelong knowledge across snapshot/restore.
- recursive discover -> goal -> act -> tool -> rediscover bootstrapping.
- active perception, intervention-aware causal discovery, and branching counterfactual imagination.
- long-horizon replanning after observed model surprise.
- self-directed curriculum selection, adaptive search allocation, and meta-learning.
- evidence-aware goal conflict resolution, goal abandonment, and unknown-unknown detection.
- benchmarked self-improvement proposals that cannot authorize their own adoption.
- a blind evaluator interface for externally supplied nonce-bound challenge commitments.

## Core boundaries

IX-Sally preserves these distinctions throughout the implementation:

- Output is not evidence.
- Memory is not truth.
- Prediction is not observation.
- Simulation is not execution.
- Capability is not authority.
- A proposal is not permission.
- A test result is not certification.
- Repetition does not convert a claim into truth.
- IX-Sally may not approve its own consequential action.
- IX-Sally may not certify itself as AGI.

## Architecture flow

```text
IX source
  -> lexer / parser / semantic validation / type checking
  -> deterministic bytecode compiler
  -> bounded virtual machine
  -> typed output, memory, failure, and trace receipt

observations and admitted evidence
  -> cognitive workspace and active memory
  -> epistemically typed world model
  -> causal inference, prediction, and counterfactuals
  -> goal graph and bounded planner
  -> executive uncertainty, risk, and authority gates
  -> cognitive proposal bridge
  -> existing IX-Sally proposal and human-review control plane

observed outcomes
  -> learning ledger and capability measures
  -> curriculum, retention, and held-out transfer records
  -> regression-aware adaptation proposal
  -> separate human decision and validation boundary
```

Detailed design documentation is available in:

- `docs/ARCHITECTURE.md`
- `docs/USAGE.md`
- `docs/AGI_CLAIM_BOUNDARY.md`
- `docs/ROADMAP_COMPLETION_LEDGER.md`
- `VALIDATION_REPORT.md`

## Repository layout

```text
IX-Sally/
├── .github/workflows/       GitHub Actions quality gates
├── docs/                    Architecture, usage, boundaries, and ledger
├── examples/                Executable IX and Python demonstrations
├── src/ix_sally/
│   ├── cognition/           Integrated cognitive runtime
│   ├── language/            IX language frontend and type system
│   └── ...                  Governed control-plane modules
├── tests/                   Complete source test inventory
├── check_green.py           Unified quality-gate runner
├── repository_check.py      Repository-integrity gate
├── dependency_check.py      Dependency-cycle gate
├── architecture_check.py    Runtime-boundary gate
├── package_smoke.py         Installed-wheel verification
├── pyproject.toml           Package and tool configuration
├── VALIDATION_REPORT.md     Exact local validation evidence and limits
└── LICENSE                  Controlling evaluation-only terms
```

## Requirements

- Python 3.11, 3.12, or 3.13
- No declared third-party runtime dependencies

Development tools are available through the `dev` extra:

```text
python -m pip install -e ".[dev]"
```

## Run the complete quality gate

```text
python check_green.py
```

Individual gates can be selected:

```text
python check_green.py --gate format
python check_green.py --gate lint
python check_green.py --gate type-check
python check_green.py --gate repository
python check_green.py --gate dependencies
python check_green.py --gate architecture
python check_green.py --gate test
python check_green.py --gate package
```

## Run the observed cognitive evaluation

```text
python -m ix_sally --cognitive-evaluation
```

The command emits canonical JSON for fifteen deterministic local benchmarks:

1. typed IX arithmetic;
2. governed VM memory;
3. grounded primitive execution;
4. active-memory retrieval;
5. causal prediction;
6. bounded planning;
7. measured transfer;
8. functional ninefold coordination;
9. human-authority blocking;
10. calibrated uncertainty;
11. executive-to-governance bridging;
12. separated held-out curriculum evidence;
13. replayable episode chaining;
14. regression-aware adaptation;
15. exact complete-state restoration.

A passing report still contains:

```text
classification = experimental-cognitive-architecture
agi_certified = false
```

## Execute IX source

Run the included example:

```text
python -m ix_sally --execute-ix examples/answer.ix
```

Example IX program:

```text
let answer = 6 * 7
remember answer = answer
print recall answer
assert answer == 42
```

The command returns a deterministic JSON receipt with typed local values,
outputs, memories, instruction trace, status, and failure information.

## Python integration

```python
from ix_sally.cognition import SallyCognitiveSystem

system = SallyCognitiveSystem.create()
result = system.execute_ix(
    "let answer = 6 * 7\nprint answer\nassert answer == 42\n",
    filename="example.ix",
)

print(result.status.value)
print(result.to_payload())
```

## Persist and restore complete state

```python
from pathlib import Path

from ix_sally.cognition import SallyCognitiveSystem, SnapshotRepository

system = SallyCognitiveSystem.create()
system.execute_ix("remember answer = 42\n", filename="memory.ix")

repository = SnapshotRepository(Path("ix-sally-state.json"))
repository.save(system.snapshot())
loaded = repository.load()
restored = SallyCognitiveSystem.from_snapshot(loaded.snapshot)

assert restored.state_payload() == system.state_payload()
```

Snapshot restoration validates canonical payloads and state digests before
reconstructing the integrated runtime. Backup recovery fails closed when no
valid copy remains.

## Local validation evidence

The final source state was locally observed with:

- CPython 3.12.14 execution;
- exactly 990 collected tests across 138 test files;
- all 990 tests passing in one complete run;
- Ruff formatting and lint checks passing;
- Mypy strict typing passing across 271 source files;
- repository integrity passing with 0 violations;
- 128 runtime modules and 676 imports with 0 dependency cycles;
- 0 architecture-boundary violations;
- installed-wheel smoke testing passing;
- all 15 built-in cognitive benchmarks passing;
- 0 Python lines over the configured 100-character limit;
- 0 trailing-whitespace findings;
- 0 source TODO/FIXME/placeholder/`pass`/`NotImplementedError` findings.

Separate local CPython 3.11 and 3.13 runs were not performed. GitHub Actions is
configured to run formatting, lint, strict typing, structural checks, tests,
and wheel verification on Python 3.11, 3.12, and 3.13.

See `VALIDATION_REPORT.md` for the exact evidence and limitations.

## AGI claim boundary

IX-Sally implements mechanisms commonly explored in cognitive architectures,
but architecture completion and local tests do not establish artificial
general intelligence.

This repository does not prove:

- human-level or open-world general intelligence;
- broad unfamiliar-task competence;
- autonomous scientific discovery;
- safe recursive self-improvement;
- robust embodiment;
- production safety;
- certification or regulatory compliance.

No external foundation-model weights, training corpus, sensor stream, robotics
stack, or proprietary benchmark data is bundled. Those are explicit external
system boundaries rather than hidden missing files.

The accurate description is:

> IX-Sally is a governed experimental cognitive runtime and research
> architecture. It is not a demonstrated AGI.

## Development status

IX-Sally remains an alpha research and evaluation build. It is intended for
architecture review, deterministic experimentation, governed-agent research,
human-authority workflow evaluation, and reproducible cognitive-runtime tests.

Do not use it to authorize real-world consequential execution without separate
engineering, security, legal, safety, operational, and human governance review.

## License

IX-Sally is source-available for evaluation and review under the terms in
`LICENSE`.

Production use, commercial use, hosted use, derivative use, funded use,
government or regulated operational use, redistribution, or ownership transfer
requires prior written permission and a paid commercial license from Bryce
Lovell.
