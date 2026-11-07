# IX-Sally 0.9.3: Developmental Cognition Research

## Research purpose

The 0.9.3 release adds an executable, persistent experimental protocol for learning
unfamiliar numeric relationships. The research question is whether evidence acquired
in one world can reduce the interactions needed in another without sacrificing
predictive accuracy, and whether incorrect knowledge can be rejected after change.
This is not a claim of artificial general intelligence.

### Implemented capabilities

- **Active observation:** the learner chooses queries to discriminate competing
  compositional programs, rather than receiving only a fixed stream of examples.
- **Original program induction:** hypotheses are executable, typed mathematical
  expression trees synthesized within a bounded grammar (channel, addition,
  subtraction, multiplication, negation and absolute value). Expressions may be
  nested to depth three, with a bounded candidate budget. The grammar is supplied
  in advance; the learner does not invent arbitrary new operators.
- **Continual experience:** separately validated concepts persist between worlds.
  A previously validated hypothesis may be retested in a different environment.
- **Contradiction recovery:** an observed mismatch rejects the reused hypothesis;
  available alternative expressions are re-evaluated against all collected evidence.
- **Unseen extrapolation:** training queries use input values in [-3, 3], whereas
  assessment inputs use distinct, more extreme values outside that range.
- **Separate baselines:** the same environment is solved by a fresh active learner
  and by a fresh passive learner, without prior concept reuse.
- **Strategy evaluation:** an active-query learning strategy is compared with
  passive querying using paired held-out performance and query cost. A favorable
  result generates a proposal for review only; it does not modify deployed code.
- **Portable learning state:** canonical JSON checkpoints preserve observation
  history, expression structures, validated concept records and a digest-linked
  episode sequence. Single-writer lock files and atomic replacement prevent
  cooperating local writers from silently overwriting each other's state.
- **Evidence integrity:** duplicate observations and contradictory expression
  histories fail validation. This catches corruption, not an attacker who can
  deliberately rewrite and rehash the entire local checkpoint. External anchoring
  and independent secret holdouts are not provided.

### Evidence hardening

The pre-existing strategy-comparison implementation previously included training
cases in its improvement calculation even when the paired holdouts were worse.
The evaluator now bases every promotion statistic on consistently labeled paired
holdouts and rejects duplicate case IDs, nonfinite errors and safety failures.

The perception quorum now rejects repeated channel IDs and repeated declared
source identities. Independent readings sharing one physical source cannot count
as two votes. Nonfinite values and invalid thresholds fail closed. Declared
source identities are not cryptographically authenticated.

### Reproduction

Requires Python 3.11 or later; no foundation-model API, GPU or external research
repository is required.

```bash
python -m pip install -e ".[dev]"
python -m ix_sally --cuc10-experiment
python -m ix_sally --cuc10-experiment --cuc10-seed 13
python -m research_gate
python check_green.py
```

To demonstrate persistence across separate program executions:

```bash
python -m ix_sally --cuc10-world multiplication-acquisition --cuc10-state research.json
python -m ix_sally --cuc10-world multiplication-transfer --cuc10-state research.json
python -m ix_sally --cuc10-world difference-regime-change --cuc10-state research.json
```

A world cannot be scored twice in one checkpoint. If an existing checkpoint
cannot be validated, it is not overwritten. A `.lock` file indicates another
write or an interrupted write. Check the process and file before removing a stale
lock. Use a new path for a new benchmark run. Do not use the transparent local
world generators as a substitute for a hidden independent evaluator.

### Local measurements

Measurements below come from executing the actual CUC-10 code, not predicted
scores. Each curriculum contains eight numeric worlds and 32 extrapolation
cases per world. Each seed changes the ordering of available input probes and
unseen evaluation inputs.

| Metric | Seed 7 | Seed 13 | Seed 29 |
| --- | ---: | ---: | ---: |
| Worlds completed | 8 | 8 | 8 |
| Continual learner mean held-out accuracy | 1.0000 | 1.0000 | 1.0000 |
| Cold-start active learner mean held-out accuracy | 1.0000 | 1.0000 | 1.0000 |
| Transfer queries saved vs cold-start | 4 | 4 | 4 |
| Rule-change recoveries | 3 | 3 | 3 |
| Re-scored historical concept accuracy | 1.0000 | 1.0000 | 1.0000 |
| Active-vs-passive normalized error improvement | 0.0675 | 0.0450 | 0.0525 |
| Automatically promoted cognitive strategies | 0 | 0 | 0 |

The active-vs-passive error metric is explicitly defined as
`0.7 * (1 - heldout_accuracy) + 0.3 * (training_queries / 10)`, where smaller
is better. The *fresh* active learner and *fresh* passive learner are compared
on each world to isolate query choice from concept transfer. The promotion
proposal requires at least five paired evaluations and at least 0.05 absolute
mean error improvement. Seed 13 falls below that proposal threshold, whereas
seeds 7 and 29 meet it. The separate CI research gate requires positive
per-seed improvement and at least 0.05 average improvement across these
three specified seeds, plus preserved authority boundaries.

After all eight worlds, the evaluation harness also re-tests retained concepts on
256 original-domain extrapolation cases. Perfect retention is expected from
immutable expression storage; it is not proof of learned neural stability.

A transfer episode uses two independent discriminative queries to check an
already validated concept; a cold-start episode uses at least three queries
while resolving new hypotheses. The four saved queries per eight-world
curriculum are consequently **protocol-dependent**. This is an observed
sample-efficiency difference on the built-in task family, not a general
transfer-learning guarantee.

### Limitations and falsification criteria

These experiments operate over two integer channels, deterministic outputs,
a known finite expression vocabulary, finite probes, transparent generators
and a narrow family of related tasks. Persisting a validated expression is
not evidence of broad continual-learning stability or resistance to
catastrophic forgetting in neural systems. Perfect scores here show the
specified task family is tractable, not that AGI has emerged.

Before stronger claims, the program must demonstrate generalization to new
operators, unpredictable structures, rich observations, noisy or partially
observable worlds, longer causal horizons, misleading correlations and truly
withheld external tasks. Independent replication, confidence calibration,
robustness studies, compute accounting and ablation results are required.

**Research classification:** `bounded-developmental-learning-experiment`.
**AGI demonstrated:** `false`.

### Authority and licensing

The new laboratory executes only pure, bounded numerical expressions and
reads/writes local research checkpoints at paths explicitly requested by its
operator. It does not issue network requests, call external services, execute
synthesized Python, authorize self-modification or independently deploy
candidate improvements. The repository's inherited source-available
research/evaluation license remains unchanged.
