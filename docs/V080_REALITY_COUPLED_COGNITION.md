# IX-Sally v0.8.0 Reality-Coupled Cognition

IX-Sally v0.8.0 adds a composed cognitive agency layer around the existing `SallyCognitiveSystem`.
The design goal is not to claim AGI. It is to make unresolved relationships with reality cause the
next cognitive operation instead of requiring a programmer to call disconnected cognition helpers.

## Core mechanism

The loop preserves four boundaries:

1. **Prediction is not observation.** A `RealityPrediction` is issued before a
   `RealityObservation` is consumed. `RealityComparator` creates an immutable `RealityDelta`.
2. **Disagreement is evidence.** `PerceptionQuorum` and `PerspectiveEnsemble` preserve channel and
   model disagreement instead of averaging it away.
3. **Failure can create a goal.** `CounterfactualGoalGenerator` turns contradiction, missing
   evidence, stale assumptions, model disagreement, or representation failure into an endogenous
   information-seeking objective.
4. **Cognition does not grant authority.** `EpistemicAuthorityEnvelope` can only narrow proposal
   scope. Consequential execution remains under the inherited governance and human-authority
   control plane.

The intended cycle is:

```text
prediction
    ↓
independent perception channels
    ↓
perception quorum + retained disagreement
    ↓
reality delta
    ↓
epistemic pressure vector
    ↓
choice of cognitive operation
    ↓
observe / discriminate / hypothesize / invent representation /
revalidate / reconsider goal / recover / shadow-test strategy
    ↓
new evidence
    ↓
updated future cognition
```

## Epistemic pressure is multidimensional

`EpistemicPressure` keeps separate causes of uncertainty:

- prediction error
- perceptual uncertainty
- model disagreement
- unresolved contradiction
- novelty
- assumption risk
- staleness
- focus omission
- goal drift
- representation failure
- causal failure
- evidence gap
- revalidation need

The selector uses the dominant *reason* for uncertainty. It does not reduce all dimensions to one
reward scalar. Exact ties use a deterministic safety-oriented priority so strong contradiction
cannot be hidden by the prediction error that produced it.

## Assumptions are first-class

`AssumptionLedger` records:

- statement
- confidence
- impact if wrong
- evidence identifiers
- age and maximum age
- validation status

Predictions can declare dependency identifiers. When reliable reality contradicts a confident
prediction, the ledger identifies implicated assumptions and marks them for contradiction or
revalidation. Aging can also trigger revalidation without waiting for an observed failure.

## Cognitive recovery

A strong contradiction can force a bounded recovery sequence:

```text
NORMAL
  ↓
COMMITMENT_HOLD
  ↓
RETRACT
  ↓
REASSESS
  ↓
REVALIDATE
  ↓
NORMAL
```

`HUMAN_REVIEW` is also available as a terminal hold when recovery cannot be completed safely.
This is deliberately different from merely lowering confidence while continuing the same chain.

## Dissent preservation

`PerspectiveEnsemble` measures disagreement while retaining minority evidence identifiers. A
minority perspective is not deleted merely because it loses a confidence-weighted majority.
Future reality can therefore vindicate a previously losing interpretation.

## Autobiographical epistemic trace

`AutobiographicalEpistemicTrace` provides an append-only causal lineage across prediction,
observation, delta, directive, goal, recovery, and learning events. It supports bounded causal
introspection such as tracing which prior events caused a later cognitive directive.

## Shadow cognitive strategies

`ShadowStrategyEvaluator` compares an incumbent and candidate strategy on shared cases. Candidate
promotion requires enough holdout cases, measured improvement, and zero recorded safety failure.
The evaluator can only produce an `eligible_for_human_review` proposal. It never auto-promotes a
cognitive strategy.

## Donor synthesis

The v0.8 mechanisms were synthesized from patterns found while auditing these donor repositories:

- IX-VisualAuthority: observation/reference comparison, directed reinspection, world-state deltas
- SynapDrive-AI: expectation/reality reconciliation, uncertainty decomposition, shadow evaluation
- IX-Autonomy-Assurance-Case-Runtime: drift, revalidation, assurance evidence, dissent retention
- IX-BlackFox-Cognition: cognitive failure detection, belief/evidence separation, bounded authority
- IX-BlackFox-WorldTwin: assumptions, branching futures, reality deltas, versioned state
- IX-HapticSight: independent channel quorum, disagreement-sensitive authority, recovery semantics
- IX-IntentRealityLoop: competing interpretation lanes, preserved focus, replayable intent/outcome loop

No donor package is imported as a runtime dependency. The implementation is native to IX-Sally and
preserves its zero-runtime-dependency package policy.

## CUC-7: Reality-Coupled Perceptual Agency

CUC-7 uses a deterministic hidden sensor world. A previously valid gain assumption is correct in
the baseline regime. The evaluator changes the gain without informing Sally. Sally then:

1. observes two reliable channels;
2. detects a high-confidence reality contradiction;
3. marks the dependent assumption contradicted;
4. enters cognitive recovery;
5. prevents an external action recommendation;
6. generates an endogenous goal to explain the contradiction;
7. records a causal trace.

Run:

```text
python -m ix_sally --cuc7-experiment
```

## CUC-8: Autonomous Epistemic Recovery

CUC-8 verifies the recovery state machine traverses hold, retract, reassess, and revalidate before
returning to normal cognition.

```text
python -m ix_sally --cuc8-experiment
```

## CUC-9: Cognitive Strategy Evolution

CUC-9 compares an incumbent and candidate cognitive strategy on shared holdout cases. A superior
candidate can become eligible for human review, but cannot auto-promote itself.

```text
python -m ix_sally --cuc9-experiment
```

## Non-claims

v0.8.0 does not demonstrate AGI, consciousness, sentience, unrestricted self-modification, general
vision, or autonomous authority. The experiments are deterministic bounded mechanisms designed to
make cognition more reality-coupled and self-correcting while preserving human control.
