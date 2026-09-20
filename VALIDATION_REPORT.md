# IX-Sally v0.7.0 Validation Report

Validation in this report records only checks actually executed on the v0.7.0 release tree in
this environment. It is not an AGI certification or independent replication.

## Release identity

- Repository: `IX-Sally`
- Package version: `0.7.0`
- Primary experiment: `CUC-6 lifelong generalization and representational freedom`
- Governance rule retained: `AI proposes. Humans decide.`

## What v0.7.0 adds over v0.6.0

### Compositional representation-language invention

The previous representation inventor searched atomic or single relational operators. v0.7.0 can
synthesize bounded multi-operation feature programs. In the CUC-6 task:

- best shallow training accuracy: `0.8125`
- invented expression: `((x0*x1)+x2)`
- program depth: `2`
- training accuracy: `1.0`
- held-out accuracy: `1.0`

The holdout uses values outside the training range. A negative-control test verifies that Sally
refuses compositional novelty when a shallow representation is already sufficient.

### Persistent online meta-learning

CUC-6 runs `12` sealed numeric worlds. The first two episodes explore both learning-strategy
families. The subsequent ten use the accumulated online meta-profile to select one strategy
before learning. All twelve observed episodes achieve held-out accuracy `1.0`.

Observed behavior:

- episode 0: two strategies evaluated
- episode 1: two strategies evaluated
- episodes 2-11: one strategy evaluated
- later strategy decisions use prior cross-domain structural evidence
- online meta-profile survives complete `SallyCognitiveSystem` snapshot/restore

This demonstrates a bounded form of later Sally changing how it learns because of earlier
experience. It does not establish open-ended universal meta-learning.

### Active lifelong knowledge maintenance

A concept that is consistently correct in one context and consistently wrong in another is
superseded by a context family and context-specific descendants. This avoids treating every
regime-dependent contradiction as a permanent exception to one over-broad concept. Low-value,
low-confidence, repeatedly contradicted items can also be retired.

### Surface-independent relational transfer

A learned topological role transfers from an industrial-control graph to a software-rendering
graph despite different entity names and relation labels. In the release challenge, the role of
`controller` is transferred to `adapter` from graph structure rather than text similarity.

### Raw-text outcome grounding

A new text-grounding path begins from unstructured strings and observed binary outcomes and
measures token information gain. In the release challenge, `glint` is discovered as the strongest
outcome-linked token. This is explicitly not general language understanding.

### Multi-goal portfolio coherence

Finite attention is allocated using current evidence, utility, information value, risk,
dependencies, and resource cost. A dependent goal is selected only after its prerequisite and a
goal whose premise collapses is abandoned.

### Bounded endurance and recovery

The integrated runtime advances the maintained lifelong store through `64` generations with
repeated consolidation, snapshots the complete cognitive state, restores it, and verifies exact
state equality including the online meta-profile and lifelong knowledge store. This is a bounded
checkpoint/recovery exercise, not evidence of long wall-clock autonomous operation.

## CUC-6 direct CLI result

Command executed:

```text
python -m ix_sally.cli --cuc6-experiment
```

Observed release-level result:

```text
release = IX-Sally-v0.7.0
demonstrated_count = 9
later_learning_is_more_selective = true
compositional representation = ((x0*x1)+x2)
compositional held-out accuracy = 1.0
agi_certified = false
```

## Automated test execution

Collected test count:

```text
1036
```

The entire collected suite was executed exhaustively in partitions because one large legacy
human-review partition can exceed this environment's individual command time limit. The executed
partitions covered:

- `tests/cognition`
- `tests/language`
- `tests/cuc1`
- `tests/cuc2`
- `tests/cuc3`
- `tests/cuc4`
- `tests/cuc5`
- `tests/cuc6`
- every root-level `tests/test_*.py` file, split into smaller exhaustive batches

All executed partitions passed. No test in the collected 1,036-test set was omitted from the
partitioned execution.

## Structural verification

Executed after generated caches were removed:

```text
repository integrity: PASS
source/test files checked by repository gate: 312
violations: 0

runtime dependency graph: PASS
runtime modules: 161
imports: 843
cycles: 0

runtime architecture: PASS
runtime modules: 161
imports: 843
boundary violations: 0
```

Python compilation/import validation and package smoke checks also passed.

`ruff` and `mypy` are not installed in this execution environment, so this report does **not**
claim those two optional development gates passed.

## Claim boundary

v0.7.0 is a stronger bounded experimental cognitive architecture than v0.6.0. It shows that prior
experience can alter later strategy selection, that representation synthesis can exceed a
one-step feature language, and that persistent cognition can repair context-dependent knowledge
and transfer relational structure across different surfaces.

It does **not** establish AGI, consciousness, free will, unrestricted self-modification, general
vision/audio perception, indefinite autonomous operation, independent replication, or an accepted
scientific AGI threshold. Independent evaluation still requires challenge sets created by parties
other than IX-Sally's builders.
