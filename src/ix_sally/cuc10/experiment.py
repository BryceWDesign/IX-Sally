"""Evaluator-owned worlds for continual learning, transfer, change and extrapolation.

Task generators, hidden rules and evaluation labels live exclusively on the
harness side. These are transparent, deterministic *local* challenges, not
independent external or undisclosed AGI benchmarks.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

from ix_sally.cognition.developmental_learning import (
    InductiveLearner,
    LearningEpisode,
    ResearchState,
)
from ix_sally.cognition.representation_programs import FeatureProgram, ProgramOperator
from ix_sally.cognition.shadow_strategies import ShadowStrategyEvaluator, StrategyOutcome
from ix_sally.digest import JsonObject, stable_digest
from ix_sally.foundation import FoundationError


def _channel(index: int) -> FeatureProgram:
    return FeatureProgram(ProgramOperator.CHANNEL, channel_index=index)


def _binary(op: ProgramOperator, left: FeatureProgram, right: FeatureProgram) -> FeatureProgram:
    return FeatureProgram(op, left=left, right=right)


def _unary(op: ProgramOperator, child: FeatureProgram) -> FeatureProgram:
    return FeatureProgram(op, left=child)


@dataclass(frozen=True, slots=True)
class _World:
    name: str
    hidden_relation: FeatureProgram

    def observe(self, x: tuple[int, int]) -> int:
        return int(self.hidden_relation.evaluate(x))


def _worlds() -> tuple[_World, ...]:
    x, y = _channel(0), _channel(1)
    product = _binary(ProgramOperator.MULTIPLY, x, y)
    difference = _binary(ProgramOperator.SUBTRACT, x, y)
    composite = _binary(ProgramOperator.ADD, product, x)
    absolute = _unary(ProgramOperator.ABS, difference)
    return (
        _World("multiplication-acquisition", product),
        _World("multiplication-transfer", product),
        _World("difference-regime-change", difference),
        _World("difference-transfer", difference),
        _World("compositional-acquisition", composite),
        _World("compositional-transfer", composite),
        _World("absolute-relation-acquisition", absolute),
        _World("absolute-relation-transfer", absolute),
    )


def available_worlds() -> tuple[str, ...]:
    return tuple(world.name for world in _worlds())


def _pools(seed: int, name: str) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Generate disjoint labeled training queries and as-yet-unseen scoring inputs."""
    # A named domain has independent deterministic sampling, even when a run order changes.
    rng = Random(f"IX-Sally:cuc10:{seed}:{name}")
    train = [(a, b) for a in range(-3, 4) for b in range(-3, 4)]
    test = [
        (a, b)
        for a in (-8, -7, -6, -5, 5, 6, 7, 8)
        for b in (-8, -7, -6, -5, 5, 6, 7, 8)
    ]
    rng.shuffle(train)
    rng.shuffle(test)
    return tuple(train[:32]), tuple(test[:32])


@dataclass(frozen=True, slots=True)
class WorldResult:
    world_id: str
    selection: str
    expression: str
    probes: int
    baseline_probes: int
    passive_probes: int
    holdout_accuracy: float
    baseline_holdout_accuracy: float
    passive_holdout_accuracy: float
    holdout_cases: int
    candidate_count: int
    training_holdout_disjoint: bool
    evidence_digest: str

    def to_payload(self) -> JsonObject:
        return {
            "world_id": self.world_id,
            "selection": self.selection,
            "expression": self.expression,
            "probes": self.probes,
            "baseline_probes": self.baseline_probes,
            "passive_probes": self.passive_probes,
            "holdout_accuracy": self.holdout_accuracy,
            "baseline_holdout_accuracy": self.baseline_holdout_accuracy,
            "passive_holdout_accuracy": self.passive_holdout_accuracy,
            "holdout_cases": self.holdout_cases,
            "candidate_count": self.candidate_count,
            "training_holdout_disjoint": self.training_holdout_disjoint,
            "evidence_digest": self.evidence_digest,
        }


def _accuracy(
    program: FeatureProgram, world: _World, heldout: tuple[tuple[int, int], ...]
) -> float:
    return round(
        sum(program.evaluate(pair) == world.observe(pair) for pair in heldout) / len(heldout),
        12,
    )


def run_world(
    state: ResearchState,
    world_id: str,
    *,
    seed: int = 7,
    budget: int = 10,
) -> tuple[ResearchState, WorldResult]:
    """Advance exactly one episode, preserving only independently scored concepts."""
    worlds = {world.name: world for world in _worlds()}
    world = worlds.get(world_id)
    if world is None:
        raise FoundationError(f"unknown research world: {world_id}")
    if world_id in {episode.world_id for episode in state.episodes}:
        raise FoundationError("research world has already been evaluated in this checkpoint")
    if budget < 3 or budget > 32:
        raise FoundationError("world budget must be between 3 and 32 queries")
    pool, heldout = _pools(seed, world.name)
    if set(pool) & set(heldout):
        raise FoundationError("evaluation labels overlap with training query pool")
    learner = InductiveLearner()
    prior = state.concepts[-1].program if state.concepts else None
    program, queried, selection, candidate_count = learner.infer(
        pool=pool, observe=world.observe, budget=budget, prior=prior
    )
    cold, cold_queries, _, _ = learner.infer(
        pool=pool, observe=world.observe, budget=budget,
    )
    passive, passive_queries, _, _ = learner.infer(
        pool=pool, observe=world.observe, budget=budget, active=False,
    )
    disjoint = not ({item.channels for item in queried} & set(heldout))
    if not disjoint:
        raise FoundationError("evaluation input was queried before scoring")
    accuracy = _accuracy(program, world, heldout)
    episode = LearningEpisode(
        world_id=world_id,
        examples=queried,
        program=program,
        selection=selection,
        candidates_remaining=candidate_count,
        heldout_accuracy=accuracy,
        heldout_cases=len(heldout),
        previous_digest=state.latest_digest,
    )
    extended = state.append(episode)
    return extended, WorldResult(
        world_id=world_id,
        selection=selection,
        expression=program.expression(),
        probes=len(queried),
        baseline_probes=len(cold_queries),
        passive_probes=len(passive_queries),
        holdout_accuracy=accuracy,
        baseline_holdout_accuracy=_accuracy(cold, world, heldout),
        passive_holdout_accuracy=_accuracy(passive, world, heldout),
        holdout_cases=len(heldout),
        candidate_count=candidate_count,
        training_holdout_disjoint=disjoint,
        evidence_digest=episode.digest,
    )


@dataclass(frozen=True, slots=True)
class DevelopmentalReport:
    seed: int
    worlds: tuple[WorldResult, ...]
    retained_concepts: int
    mean_accuracy: float
    mean_baseline_accuracy: float
    mean_passive_accuracy: float
    transfer_probe_savings: int
    regime_recoveries: int
    retention_accuracy: float
    retention_cases: int
    state_digest: str
    strategy_improvement: float
    strategy_holdouts: int
    strategy_review_eligible: bool
    strategy_auto_promoted: bool = False
    classification: str = "bounded-developmental-learning-experiment"
    agi_demonstrated: bool = False

    def to_payload(self) -> JsonObject:
        return {
            "seed": self.seed,
            "worlds": [item.to_payload() for item in self.worlds],
            "retained_concepts": self.retained_concepts,
            "mean_accuracy": self.mean_accuracy,
            "mean_baseline_accuracy": self.mean_baseline_accuracy,
            "mean_passive_accuracy": self.mean_passive_accuracy,
            "transfer_probe_savings": self.transfer_probe_savings,
            "regime_recoveries": self.regime_recoveries,
            "retention_accuracy": self.retention_accuracy,
            "retention_cases": self.retention_cases,
            "state_digest": self.state_digest,
            "strategy_improvement": self.strategy_improvement,
            "strategy_holdouts": self.strategy_holdouts,
            "strategy_review_eligible": self.strategy_review_eligible,
            "strategy_auto_promoted": self.strategy_auto_promoted,
            "classification": self.classification,
            "agi_demonstrated": self.agi_demonstrated,
        }


def run_developmental_experiment(seed: int = 7) -> tuple[DevelopmentalReport, ResearchState]:
    """Run the full reproducible curriculum, including cold and passive ablations."""
    state = ResearchState()
    outcomes: list[WorldResult] = []
    for world_id in available_worlds():
        state, outcome = run_world(state, world_id, seed=seed)
        outcomes.append(outcome)
    transfers = [item for item in outcomes if item.selection == "transferred"]
    # Strategies receive the same world and held-out cases. Only query selection differs:
    # both start each world without prior knowledge. Lower error balances prediction and
    # experimentation cost; training data never contributes to this comparison.
    strategy_outcomes = tuple(
        evidence
        for row in outcomes
        for evidence in (
            StrategyOutcome(
                "passive", row.world_id,
                0.7 * (1.0 - row.passive_holdout_accuracy) + 0.3 * row.passive_probes / 10,
                True,
            ),
            StrategyOutcome(
                "active", row.world_id,
                0.7 * (1.0 - row.baseline_holdout_accuracy) + 0.3 * row.baseline_probes / 10,
                True,
            ),
        )
    )
    proposal = ShadowStrategyEvaluator().evaluate(
        incumbent_id="passive", candidate_id="active", outcomes=strategy_outcomes,
        minimum_holdouts=5, minimum_improvement=0.05,
    )
    # Evaluate every earlier concept again after the whole sequence, without updating it.
    worlds_by_name = {world.name: world for world in _worlds()}
    retention_scores = tuple(
        _accuracy(
            episode.program,
            worlds_by_name[episode.world_id],
            _pools(seed, episode.world_id)[1],
        )
        for episode in state.episodes
    )
    report = DevelopmentalReport(
        seed=seed,
        worlds=tuple(outcomes),
        retained_concepts=len(state.concepts),
        mean_accuracy=round(sum(item.holdout_accuracy for item in outcomes) / len(outcomes), 12),
        mean_baseline_accuracy=round(
            sum(item.baseline_holdout_accuracy for item in outcomes) / len(outcomes), 12
        ),
        mean_passive_accuracy=round(
            sum(item.passive_holdout_accuracy for item in outcomes) / len(outcomes), 12
        ),
        transfer_probe_savings=sum(item.baseline_probes - item.probes for item in transfers),
        regime_recoveries=sum(item.selection == "recovered" for item in outcomes),
        retention_accuracy=round(sum(retention_scores) / len(retention_scores), 12),
        retention_cases=sum(item.holdout_cases for item in outcomes),
        state_digest=stable_digest(state.to_payload()),
        strategy_improvement=proposal.improvement,
        strategy_holdouts=proposal.holdout_cases,
        strategy_review_eligible=proposal.eligible_for_human_review,
    )
    return report, state
