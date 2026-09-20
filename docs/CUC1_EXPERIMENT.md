# Choice Under Consequence 1

## Purpose

CUC-1 is IX-Sally's first experiment in acquired causal competence. It tests a
narrow but necessary property of an AGI-directed system:

> Can measured consequences alter the system's internal causal model, produce
> an executable skill, and change a later decision on an observation withheld
> from training?

CUC-1 is not an AGI benchmark. It replaces scripted demonstrations in which an
expected action is available to the candidate or success is supplied by fixture
code.

## Environment boundary

The environment privately selects one of four rotational causal rules. A public
observation contains its identity, causal-family identity, visible cue,
context, four available actions, and evidence digest.

It contains no expected action, answer, reward, target, rule, or rotation value.
The evaluator consumes each observation exactly once and computes the
consequence from its committed private rule.

The rule commitment is available before interaction. The rule itself is
revealed only after all active observations are consumed.

## Learner

The learner begins with four equally probable causal hypotheses:

```text
action = rotate(cue, 0)
action = rotate(cue, 1)
action = rotate(cue, 2)
action = rotate(cue, 3)
```

Every action receives a complete score vector: expected success, expected
information gain, novelty, reversibility, cost, risk, and internal selection
score. The full vector is preserved in the choice receipt.

The learner revises all hypothesis probabilities after every measured success
or failure. When a hypothesis exceeds the promotion threshold and has multiple
consequence records, it is compiled into an executable skill. The skill applies
the learned transformation to a new cue; it is not a description of success.

## Counterfactual proof

The experiment retains a frozen pre-learning agent. Both agents receive the
exact same held-out observation. The report records their actions, whether
behavior changed, whether the learned agent invoked its skill, and the measured
held-out consequence.

The strict claim fails if behavior did not change or if the changed behavior
did not succeed.

## Default run

The default seed commits the evaluator to a half-turn rule without exposing it
to the learner:

1. choose `north` for a north cue, fail;
2. choose `south` for an east cue, fail;
3. choose `east` for a south cue, fail;
4. promote the remaining high-confidence half-turn hypothesis;
5. invoke the skill for a north cue, choose `south`, succeed;
6. receive the held-out west cue, invoke the skill, choose `east`, succeed.

The frozen agent chooses `north` on the held-out west cue. Measured experience
therefore changes the later action from `north` to `east`.

## Strict success predicate

`acquired_competence` is true only when public-payload leakage checks pass, an
executable skill exists, every training consequence changes agent state, the
frozen and learned choices differ on the same held-out observation, the learned
choice succeeds, and that choice explicitly uses the learned skill.

The report fixes `agi_certified` to `false`.

## Falsification conditions

The bounded claim is falsified by answer leakage, observation reuse, broken
observation/action bindings, non-normalized beliefs, failure to form a skill,
failed held-out transfer, unchanged pre/post behavior, non-determinism for the
same seed, or disagreement between the evaluator commitment and post-run reveal.

## Known limits

- Only four discrete causal hypotheses are considered.
- Perception is symbolic rather than learned from pixels or sensors.
- Transfer is across observations inside one causal family.
- There is no continual-learning or catastrophic-forgetting challenge.
- There is no open-ended environment generation.
- There is no learned neural world model.
- There is no external real-world actuation.
- The experiment has not been independently replicated.

## Next experiment

CUC-2 should remove the fixed hypothesis catalog. It should synthesize candidate
programs from trajectories, test them in procedurally generated object worlds,
retain context-dependent rules, and compose skills across hidden task families.
