# IX-Sally Architecture

## System identity

IX-Sally is one standalone Python modular monolith. The repository combines two
connected systems:

1. A deterministic, receipt-driven governance control plane for proposal,
   evidence, execution, human review, resume, audited reentry, and closeout.
2. A bounded experimental cognitive runtime for typed language execution,
   attention, memory, world modeling, planning, learning, metacognition, and
   proposal generation.

The cognitive runtime does not bypass the original control plane. A cognitive
plan enters the existing proposal path through an explicit bridge. Execution,
permission, evidence admission, and human authority remain separate concerns.

## Governing invariants

The architecture is built around these non-negotiable boundaries:

- Output is not evidence.
- Memory is not truth.
- Capability is not authority.
- A proposal is not permission.
- A simulation is not an observed outcome.
- A test result is not certification.
- IX-Sally may not approve its own consequential action.
- IX-Sally may not certify itself as AGI.

## Data-flow overview

```text
IX source
  -> lexer / parser / semantic validation
  -> typed bytecode compiler
  -> bounded virtual machine
  -> execution receipt and trace

observations / evidence
  -> workspace and active memory
  -> epistemically typed world model
  -> causal inference and prediction
  -> bounded deterministic planner
  -> executive risk / uncertainty / authority gates
  -> cognitive proposal bridge
  -> existing IX-Sally proposal and human-authority control plane

outcomes
  -> learning ledger
  -> capability measures
  -> curriculum and held-out transfer records
  -> regression-aware adaptation proposal
  -> human decision and validation boundary
```

## Language and execution

The `ix_sally.language` package provides source spans, diagnostics, tokens, a
lexer, expression and statement ASTs, parsing, semantic validation, type
inference, and program type checking.

The `ix_sally.cognition` execution layer adds:

- `CognitiveValue`: exact scalar values with explicit type identity.
- `Instruction` and `BytecodeProgram`: deterministic typed instructions.
- `IXCompiler`: compilation from validated IX AST to bounded bytecode.
- `IXVirtualMachine`: step-limited execution with no arbitrary Python callback.
- `VMResult`: immutable status, output, memory, failure, and trace receipt.

VM memory is committed to the integrated system only after a clean halt. A
failed assertion or runtime failure cannot partially overwrite committed
runtime memory.

## Grounded primitives

`PrimitiveRegistry` contains a closed catalog of validated primitive
operations. Each primitive records:

- canonical identity;
- arity;
- operation kind;
- lifecycle status;
- grounding evidence;
- validation evidence;
- an explicit reason when unavailable or rejected.

`PrimitiveExecutor` dispatches only enumerated operations. It does not accept
runtime-supplied Python callables, dynamic imports, or arbitrary code strings.

## Cognitive workspace

`CognitiveWorkspace` is a bounded immutable attention surface. Workspace items
have explicit kinds, confidence, salience, status, provenance, and parent
links. Admission is deterministic and capacity-limited.

Beliefs, hypotheses, goals, risks, observations, and decisions are represented
as different item kinds rather than being collapsed into untyped text.

## Active memory

`ActiveMemoryStore` separates four memory layers:

- working;
- episodic;
- semantic;
- procedural.

Every entry has a truth status, confidence, sequence number, evidence digests,
source links, tags, and an optional reason. Retrieval uses a transparent lexical
score. Truth-only retrieval excludes pending, stale, contradicted, and
quarantined entries.

Consolidation never converts repetition into truth. Evidence and status remain
required.

## Replayable episodes

`EpisodeLedger` is an append-only chain of complete cognitive episodes. Each
episode records:

- initial and final state digests;
- ordered steps;
- input and output evidence links;
- completion, block, failure, or skip status;
- the previous episode digest.

Sequence numbers and previous-digest links are validated before admission.

## World model

`WorldModel` distinguishes:

- observed facts;
- inferred facts;
- predicted facts;
- hypothetical facts;
- contradicted facts.

`CausalRule` requires evidence and preserves the epistemic status of derived
facts. Prediction and counterfactual simulation do not rewrite predictions or
hypotheses as observations.

## Goals and planning

`GoalGraph` provides dependency-aware goal selection with explicit lifecycle,
priority, utility, risk limit, authority metadata, and desired world state.
Dependency cycles and missing prerequisites fail closed.

`DeterministicPlanner` performs bounded exact-state search over declarative
actions. `ActionSpec` records preconditions, effects, cost, risk, and whether
human authority is required.

`PlanSimulator` creates hypothetical result states and a permission receipt. It
does not perform external side effects.

## Calibrated uncertainty

`UncertaintyLedger` records forecast probabilities and observed outcomes. It
produces:

- Brier score;
- fixed-bin calibration summaries;
- expected calibration error;
- capability-specific reports.

An empty report remains a zero-sample report, not proof of perfect calibration.
The executive controller can block planning when observed calibration error
exceeds its declared threshold.

## Executive control

`ExecutiveController`:

1. reconciles goals against the world model;
2. selects one eligible goal;
3. checks calibration;
4. asks the bounded planner for a plan;
5. checks explicit workspace risks;
6. checks the goal risk limit;
7. checks human-authority requirements;
8. emits a decision receipt.

The possible outcomes include no goal, satisfied goal, plan ready, requires
human authority, blocked risk, blocked uncertainty, and plan not found.

It proposes. It does not execute.

## Governance bridge

`CognitiveProposalBridge` converts a plan-ready executive decision into the
repository's existing `SallyProposalPacket` and `ProposalAction` records.

The bridge preserves:

- action identity;
- selected-goal rationale;
- supporting evidence;
- human-boundary metadata;
- decision-to-proposal digest links.

Blocked decisions cannot enter the proposal path.

## Learning and transfer

`LearningLedger` records evidence-bound outcomes by skill and task family.
`SkillProfile` exposes observed performance rather than inferred competence.
`TransferEvaluation` separates familiar, novel, and retention scores.

`CurriculumLedger` adds:

- training, validation, and held-out task splits;
- task prerequisites;
- required capability labels;
- pass thresholds;
- observed trials;
- split scores;
- an explicit validation-to-held-out transfer gap.

Held-out results are not merged into training results.

## Metacognition and adaptation

`SelfModel` contains only measured capability records with evidence and stated
limitations. It may identify the weakest measured capability.

`AdaptationController` can propose a bounded improvement and compare complete
before/after capability measurements. It explicitly detects:

- improvement;
- neutral change;
- regression;
- incomplete measurement.

An adaptation proposal remains proposed until a separate human decision.
Regression or incomplete evaluation blocks validation advancement.

## Functional ninefold

`NinefoldCoordinator` runs the repository's nine canonical roles as distinct
cognitive functions. It does not simulate nine personalities or use unbounded
agent conversation. Each role emits one typed finding within the same bounded
cycle and shared evidence state.

## Persistence and recovery

`CognitiveSnapshot` serializes the complete integrated state into canonical JSON
with a SHA-256 state digest.

`SallyCognitiveSystem.from_snapshot` reconstructs and validates every extended
subsystem, including:

- workspace;
- memory;
- world model;
- action catalog;
- learning;
- self model;
- goals;
- calibration ledger;
- episode chain;
- curriculum;
- primitive registry;
- VM memories;
- counters.

`SnapshotRepository` writes through a temporary file, flushes the file, uses
atomic replacement where the operating system provides it, maintains a prior
backup, and verifies saved bytes before reporting success. It does not claim
hardware-level durability that Python or the host filesystem cannot prove.

## Evaluation

`run_core_evaluation()` executes fifteen deterministic observed checks covering:

1. typed IX arithmetic;
2. governed VM memory;
3. grounded primitives;
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

The evaluation report contains `agi_certified: false` by construction.

## Dependency posture

The runtime declares zero third-party dependencies. Development gates use
Pytest, Ruff, and Mypy as optional development tools. The package targets Python
3.11, 3.12, and 3.13.
