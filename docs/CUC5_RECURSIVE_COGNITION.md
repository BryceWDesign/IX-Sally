# CUC-5 Recursive Cognitive Bootstrapping

CUC-5 is IX-Sally v0.6.0's integration challenge. It is designed to prevent a collection of isolated cognitive mechanisms from being mistaken for a general system. The experiment forces discoveries from one mechanism to become inputs to later cognition.

## Central loop

```text
raw observations
  -> atomic representation fails
  -> invent alternative representation
  -> holdout validation
  -> promote opaque semantic primitive
  -> persist discovery
  -> author an internal goal after the discovery exists
  -> construct an action for that goal
  -> validate and forge the action into a reusable tool
  -> observe structured high-confidence failures
  -> detect a possible unknown unknown
  -> invent and validate a second, different representation
  -> persist the second discovery
```

The default CUC-5 run produces a first nonlinear `product` representation and a later `abs_difference` representation. Those names identify the generated feature operators for auditability; Sally is not supplied a human semantic label for the resulting concepts.

## Additional bounded mechanisms

CUC-5 also exercises:

- representation invention beyond atomic raw channels;
- semantic primitive promotion after held-out validation;
- long-horizon planning with model surprise and replanning;
- structural transfer across two different surface domains;
- self-directed curriculum selection from measured weakness and uncertainty;
- persistent lifelong knowledge, revision, consolidation, and snapshot restoration;
- ontology restructuring when multiple concepts share one predictive signature;
- intervention-aware causal discovery, possible confounding, and regime-change detection;
- raw numeric stream grounding into continuous features and change events;
- active perception by expected information gain;
- branching counterfactual imagination;
- held-out validation before a discovered procedure becomes a reusable tool;
- confidence-vs-performance self-diagnosis;
- benchmarked self-improvement proposals that remain human-authority gated;
- evidence-aware conflict resolution among incompatible goals;
- explicit goal abandonment when premises or utility collapse;
- unknown-unknown signals from clustered high-confidence residuals;
- learned allocation of finite search budget;
- meta-learning that can change the strategy selected for future tasks;
- a second structurally different unfamiliar representation challenge;
- a nonce-bound blind-evaluator interface for challenge sets supplied by third parties.

## What is deliberately not claimed

CUC-5 does not prove AGI, consciousness, free will, or unrestricted ontology creation. Its representation grammar, search horizons, procedural environments, numeric stream grounder, and compute budgets are finite. The repository includes a blind-evaluator interface, but tests authored by IX-Sally's builders are not independent validation. Real-world vision/audio grounding, open internet operation, external resource acquisition, shutdown resistance, unilateral deployment, and self-authorized code adoption are not enabled by this experiment.

## Authority boundary

Cognitive search may be generative. External authority is not. Self-improvement results are proposals backed by benchmarks. They cannot authorize their own adoption. Existing IX-Sally control-plane and human-review boundaries remain intact.

## Run

```text
python -m ix_sally --cuc5-experiment
```

A successful run returns canonical JSON with `demonstrated_count` equal to `22`, `recursive_cognitive_growth` true, and `agi_certified` false.
