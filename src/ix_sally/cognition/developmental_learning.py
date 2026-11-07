"""Bounded continual program induction with observable experiments and durable evidence.

This laboratory learns deterministic two-channel numeric relationships from queried
outcomes. The expression operators are supplied; only their compositions are learned.
It does not execute generated source, issue external actions, or change its authority.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from typing import cast

from ix_sally.cognition.representation_programs import (
    FeatureProgram,
    ProgramOperator,
    RepresentationProgramInventor,
)
from ix_sally.digest import JsonObject, JsonValue, stable_digest, stable_json
from ix_sally.foundation import FoundationError, require_text

STATE_SCHEMA = 1
MAX_EPISODES = 256
MAX_PROGRAM_DEPTH = 3


@dataclass(frozen=True, slots=True)
class NumericExample:
    """One real query to a bounded numeric environment."""

    channels: tuple[int, int]
    consequence: int

    def to_payload(self) -> JsonObject:
        return {"channels": list(self.channels), "consequence": self.consequence}


@dataclass(frozen=True, slots=True)
class LearnedConcept:
    """A previously tested expression, never an automatically authorized action."""

    origin: str
    program: FeatureProgram
    heldout_accuracy: float
    heldout_cases: int

    def __post_init__(self) -> None:
        require_text(self.origin, field_name="origin")
        if self.program.depth > MAX_PROGRAM_DEPTH:
            raise FoundationError("concept exceeds permitted expression depth")
        if not isfinite(self.heldout_accuracy) or not 0 <= self.heldout_accuracy <= 1:
            raise FoundationError("concept accuracy must be finite and bounded")
        if self.heldout_cases < 1:
            raise FoundationError("concept needs a nonempty evaluation set")

    def to_payload(self) -> JsonObject:
        return {
            "origin": self.origin,
            "program": self.program.to_payload(),
            "heldout_accuracy": self.heldout_accuracy,
            "heldout_cases": self.heldout_cases,
        }


@dataclass(frozen=True, slots=True)
class LearningEpisode:
    """Retains experiments, hypothesis selection, and separately scored future cases."""

    world_id: str
    examples: tuple[NumericExample, ...]
    program: FeatureProgram
    selection: str
    candidates_remaining: int
    heldout_accuracy: float
    heldout_cases: int
    previous_digest: str

    def __post_init__(self) -> None:
        require_text(self.world_id, field_name="world_id")
        if self.selection not in {"induced", "transferred", "recovered"}:
            raise FoundationError("unknown model-selection mode")
        if not self.examples or len({item.channels for item in self.examples}) != len(
            self.examples
        ):
            raise FoundationError("learning episode requires unique queried inputs")
        if self.program.depth > MAX_PROGRAM_DEPTH or self.candidates_remaining < 1:
            raise FoundationError("learning hypothesis must be bounded and nonempty")
        if not isfinite(self.heldout_accuracy) or not 0 <= self.heldout_accuracy <= 1:
            raise FoundationError("episode accuracy must be finite and bounded")
        if self.heldout_cases < 1:
            raise FoundationError("episode needs unseen evaluation cases")
        if len(self.previous_digest) != 64:
            raise FoundationError("invalid evidence predecessor digest")
        if any(
            self.program.evaluate(example.channels) != example.consequence
            for example in self.examples
        ):
            raise FoundationError("selected expression contradicts its training evidence")

    def to_payload(self) -> JsonObject:
        return {
            "world_id": self.world_id,
            "examples": [item.to_payload() for item in self.examples],
            "program": self.program.to_payload(),
            "selection": self.selection,
            "candidates_remaining": self.candidates_remaining,
            "heldout_accuracy": self.heldout_accuracy,
            "heldout_cases": self.heldout_cases,
            "previous_digest": self.previous_digest,
        }

    @property
    def digest(self) -> str:
        return stable_digest(self.to_payload())


@dataclass(frozen=True, slots=True)
class ResearchState:
    """Versioned cognitive experience with a deterministic digest-linked history."""

    episodes: tuple[LearningEpisode, ...] = ()
    concepts: tuple[LearnedConcept, ...] = ()

    def __post_init__(self) -> None:
        if len(self.episodes) > MAX_EPISODES:
            raise FoundationError("research state exceeded bounded episode capacity")
        if len({episode.world_id for episode in self.episodes}) != len(self.episodes):
            raise FoundationError("duplicate experimental world")
        predecessor = "0" * 64
        for episode in self.episodes:
            if episode.previous_digest != predecessor:
                raise FoundationError("broken experimental evidence chain")
            predecessor = episode.digest
        if self.concepts != tuple(
            LearnedConcept(e.world_id, e.program, e.heldout_accuracy, e.heldout_cases)
            for e in self.episodes
            if e.heldout_accuracy == 1.0
        ):
            raise FoundationError("concept library must match successfully evaluated episodes")

    @property
    def latest_digest(self) -> str:
        return self.episodes[-1].digest if self.episodes else "0" * 64

    def append(self, episode: LearningEpisode) -> ResearchState:
        if episode.previous_digest != self.latest_digest:
            raise FoundationError("episode does not extend the expected evidence chain")
        concepts = self.concepts
        if episode.heldout_accuracy == 1.0:
            concepts = (*concepts, LearnedConcept(
                episode.world_id, episode.program, episode.heldout_accuracy,
                episode.heldout_cases,
            ))
        return ResearchState((*self.episodes, episode), concepts)

    def to_payload(self) -> JsonObject:
        content: JsonObject = {
            "schema": STATE_SCHEMA,
            "episodes": [episode.to_payload() for episode in self.episodes],
            "concepts": [concept.to_payload() for concept in self.concepts],
        }
        return {**content, "content_digest": stable_digest(content)}

    def to_json(self) -> str:
        return stable_json(self.to_payload())

    @classmethod
    def from_json(cls, value: str) -> ResearchState:
        if len(value) > 2_000_000:
            raise FoundationError("research checkpoint exceeds size limit")
        try:
            raw: JsonValue = json.loads(value)
        except (ValueError, TypeError) as exc:
            raise FoundationError("research checkpoint is invalid JSON") from exc
        if not isinstance(raw, dict):
            raise FoundationError("checkpoint must be a JSON object")
        if raw.get("schema") != STATE_SCHEMA:
            raise FoundationError("unsupported research checkpoint schema")
        digest = raw.get("content_digest")
        content = {key: item for key, item in raw.items() if key != "content_digest"}
        if not isinstance(digest, str) or digest != stable_digest(content):
            raise FoundationError("research checkpoint digest mismatch")
        episodes_raw = raw.get("episodes")
        concepts_raw = raw.get("concepts")
        if not isinstance(episodes_raw, list) or not isinstance(concepts_raw, list):
            raise FoundationError("checkpoint episode and concept records must be arrays")
        if len(episodes_raw) > MAX_EPISODES or len(concepts_raw) > MAX_EPISODES:
            raise FoundationError("checkpoint exceeds record limits")
        episodes = tuple(_read_episode(item) for item in episodes_raw)
        concepts = tuple(_read_concept(item) for item in concepts_raw)
        return cls(episodes, concepts)


def _read_program(raw: object, *, depth: int = 0) -> FeatureProgram:
    if not isinstance(raw, dict) or depth > MAX_PROGRAM_DEPTH:
        raise FoundationError("invalid serialized expression")
    try:
        operator = ProgramOperator(raw.get("operator"))
        channel = raw.get("channel_index")
        left_raw = raw.get("left")
        right_raw = raw.get("right")
        if channel is not None and (type(channel) is not int or not 0 <= channel < 2):
            raise FoundationError("invalid serialized channel")
        left = _read_program(left_raw, depth=depth + 1) if left_raw is not None else None
        right = _read_program(right_raw, depth=depth + 1) if right_raw is not None else None
        program = FeatureProgram(operator, channel, left, right)
        if program.depth > MAX_PROGRAM_DEPTH or program.to_payload() != raw:
            raise FoundationError("noncanonical serialized expression")
        return program
    except (ValueError, TypeError) as exc:
        raise FoundationError("invalid serialized expression operator") from exc


def _read_example(raw: object) -> NumericExample:
    if not isinstance(raw, dict):
        raise FoundationError("invalid experimental observation")
    pair = raw.get("channels")
    result = raw.get("consequence")
    if (
        not isinstance(pair, list)
        or len(pair) != 2
        or any(type(number) is not int or not -100 <= number <= 100 for number in pair)
        or type(result) is not int
        or not -1_000_000 <= result <= 1_000_000
    ):
        raise FoundationError("experimental observation contains invalid numbers")
    return NumericExample((cast(int, pair[0]), cast(int, pair[1])), result)


def _read_episode(raw: object) -> LearningEpisode:
    if not isinstance(raw, dict) or not isinstance(raw.get("examples"), list):
        raise FoundationError("invalid serialized episode")
    examples_raw = cast(list[object], raw["examples"])
    if len(examples_raw) > 128:
        raise FoundationError("episode contains too many observations")
    try:
        return LearningEpisode(
            world_id=cast(str, raw["world_id"]),
            examples=tuple(_read_example(item) for item in examples_raw),
            program=_read_program(raw["program"]),
            selection=cast(str, raw["selection"]),
            candidates_remaining=cast(int, raw["candidates_remaining"]),
            heldout_accuracy=cast(float, raw["heldout_accuracy"]),
            heldout_cases=cast(int, raw["heldout_cases"]),
            previous_digest=cast(str, raw["previous_digest"]),
        )
    except (KeyError, TypeError) as exc:
        raise FoundationError("incomplete serialized learning episode") from exc


def _read_concept(raw: object) -> LearnedConcept:
    if not isinstance(raw, dict):
        raise FoundationError("invalid serialized concept")
    try:
        return LearnedConcept(
            origin=cast(str, raw["origin"]),
            program=_read_program(raw["program"]),
            heldout_accuracy=cast(float, raw["heldout_accuracy"]),
            heldout_cases=cast(int, raw["heldout_cases"]),
        )
    except (KeyError, TypeError) as exc:
        raise FoundationError("incomplete serialized learning concept") from exc


class InductiveLearner:
    """Query a novel numeric relation; propose hypotheses without seeing evaluation labels."""

    def __init__(self) -> None:
        inventor = RepresentationProgramInventor()
        all_programs = inventor._generate(arity=2, max_depth=3, max_candidates=4096)
        basis = ((-3, 2), (-2, -1), (-1, 3), (0, 0), (1, -2), (2, 3), (3, 1))
        signatures: set[tuple[float, ...]] = set()
        unique: list[FeatureProgram] = []
        for program in sorted(all_programs, key=lambda p: (p.complexity, p.expression())):
            signature = tuple(program.evaluate(pair) for pair in basis)
            if signature not in signatures:
                signatures.add(signature)
                unique.append(program)
        self._hypotheses = tuple(unique)

    def infer(
        self,
        *,
        pool: tuple[tuple[int, int], ...],
        observe: Callable[[tuple[int, int]], int],
        budget: int = 10,
        prior: FeatureProgram | None = None,
        minimum_transfer_probes: int = 2,
        active: bool = True,
    ) -> tuple[FeatureProgram, tuple[NumericExample, ...], str, int]:
        """Learn from active queries. `observe` is the sole source of outcome labels."""
        if budget < 1 or budget > len(pool) or len(set(pool)) != len(pool):
            raise FoundationError("invalid or duplicated probe pool")
        if minimum_transfer_probes < 2 or minimum_transfer_probes > budget:
            raise FoundationError("invalid transfer validation budget")
        available = list(self._hypotheses)
        tested: list[NumericExample] = []
        prior_active = prior is not None and prior.depth <= MAX_PROGRAM_DEPTH
        selection = "induced"
        for _ in range(budget):
            tested_pairs = {example.channels for example in tested}
            remaining_pool = tuple(pair for pair in pool if pair not in tested_pairs)
            if not active:
                pair = remaining_pool[0]
            elif prior_active and prior is not None:
                # Choose a probe with maximum disagreement *against* the prior candidate.
                pair = max(
                    remaining_pool,
                    key=lambda x: (
                        sum(model.evaluate(x) != prior.evaluate(x) for model in available),
                        -abs(x[0]) - abs(x[1]),
                        x,
                    ),
                )
            else:
                pair = max(
                    remaining_pool,
                    key=lambda x: (
                        len({model.evaluate(x) for model in available}),
                        -abs(x[0]) - abs(x[1]),
                        x,
                    ),
                )
            result = observe(pair)
            if (
                not isinstance(result, int)
                or isinstance(result, bool)
                or not -1_000_000 <= result <= 1_000_000
            ):
                raise FoundationError("observation returned an invalid consequence")
            tested.append(NumericExample(pair, result))
            available = [model for model in available if model.evaluate(pair) == result]
            if not available:
                raise FoundationError("no hypothesis matches observed reality; abstaining")
            if prior_active and prior is not None:
                if prior.evaluate(pair) != result:
                    prior_active = False
                    selection = "recovered"
                elif len(tested) >= minimum_transfer_probes:
                    return prior, tuple(tested), "transferred", len(available)
            if not prior_active and len(tested) >= 3:
                # All remaining models must make the same predictions on unqueried probes.
                if all(
                    len({model.evaluate(x) for model in available}) == 1
                    for x in remaining_pool
                ):
                    break
        winner = min(available, key=lambda p: (p.complexity, p.expression()))
        if any(winner.evaluate(item.channels) != item.consequence for item in tested):
            raise FoundationError("candidate contradicts observed training outcomes")
        return winner, tuple(tested), selection, len(available)
