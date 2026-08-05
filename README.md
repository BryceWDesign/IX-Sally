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

- CPython 3.13.5 compilation across `src`, `tests`, and `examples`;
- exactly 969 collected tests across 135 test files;
- all 969 tests passing in four balanced shards;
- repository integrity passing with 0 violations;
- 123 runtime modules and 655 imports with 0 dependency cycles;
- 0 architecture-boundary violations;
- installed-wheel smoke testing passing;
- all 15 built-in cognitive benchmarks passing;
- 0 Python lines over the configured 100-character limit;
- 0 trailing-whitespace findings;
- 0 source TODO/FIXME/placeholder/`pass`/`NotImplementedError` findings.

Ruff, Mypy, CPython 3.11, and CPython 3.12 were not available in the local
execution environment and are not falsely reported as passed. GitHub Actions is
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
