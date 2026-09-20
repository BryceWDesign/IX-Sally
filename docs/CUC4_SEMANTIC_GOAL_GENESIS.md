# CUC-4: Semantic Genesis and Open Goal Authorship

CUC-4 tests two capabilities that were absent from IX-Sally v0.4.0.

## Semantic genesis

Sally receives raw numeric channels and observed binary consequences, not a human semantic
label and not a catalog of candidate concepts. The engine measures the strongest explanation
available from any single raw channel, then searches bounded relational projections. A new
opaque concept is admitted only when it materially improves prediction over that atomic
vocabulary. The concept is provisional until it succeeds on observations withheld from the
invention process.

Reference training data produce the machine token `latent-6fb4057aa2931a9e`. Its learned
relation uses both raw channels, reaches `1.0` training accuracy, improves over the best
single-channel accuracy of `0.666666...`, and reaches `1.0` on four held-out observations.
The token intentionally has no human semantic label. Its meaning is operational: the
relation it detects, the consequences it predicts, and the evidence that can falsify it.

This is bounded semantic formation from raw relational structure. It is stronger than
renaming a known composition, but it is not unrestricted ontology invention from arbitrary
real-world modalities.

## Open goal authorship

The open-goal engine has no enum of allowed goal kinds and receives no desired target value.
It receives a start state, reusable transformations, known states, intrinsic drive weights,
and explicit search/risk bounds. It generates reachable counterfactual states and may turn
one into a new internal goal using novelty, information value, competence expansion,
simplicity, reversibility, and risk.

In the reference run, Sally starts at state `2`. States `2`, `3`, `4`, and `-2` are already
known. Without being given a target, Sally authors state `5` as its first internal target via
`double -> increment`. After that target is added to experience, the next cycle authors a
different target, `-5`, via `negate`.

Generated goals are internal cognitive-sandbox proposals. They do not authorize spending,
resource acquisition, shutdown resistance, network activity, self-deployment, or any other
external consequential action.

## Claim boundary

CUC-4 demonstrates bounded autonomous semantic formation and runtime authorship of internal
goal content. It does not demonstrate AGI, consciousness, unconstrained self-created terminal
values, unrestricted semantic invention, or unilateral external agency.
