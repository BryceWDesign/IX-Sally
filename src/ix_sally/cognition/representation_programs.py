"""Compositional representation-language invention.

IX-Sally v0.6 could replace atomic features with one invented relation.  This module
pushes that boundary by allowing Sally to synthesize small *programs* over raw channels.
The grammar is fixed for safety and tractability, but complete representations are not
pre-enumerated and can contain multiple operations.  Candidates are judged against a
simpler one-operation baseline and must survive held-out validation.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import StrEnum
from math import isfinite

from ix_sally.cognition.representation import RepresentationObservation
from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import FoundationError, require_text


class ProgramOperator(StrEnum):
    CHANNEL = "channel"
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    ABS = "abs"
    NEGATE = "negate"


@dataclass(frozen=True, slots=True)
class FeatureProgram:
    """One executable representation expression."""

    operator: ProgramOperator
    channel_index: int | None = None
    left: FeatureProgram | None = None
    right: FeatureProgram | None = None

    def __post_init__(self) -> None:
        if self.operator is ProgramOperator.CHANNEL:
            if self.channel_index is None or self.channel_index < 0:
                raise FoundationError("channel feature requires a non-negative index")
            if self.left is not None or self.right is not None:
                raise FoundationError("channel feature cannot contain child programs")
            return
        if self.operator in {ProgramOperator.ABS, ProgramOperator.NEGATE}:
            if self.left is None or self.right is not None:
                raise FoundationError("unary feature requires exactly one child")
            return
        if self.left is None or self.right is None:
            raise FoundationError("binary feature requires two children")

    @property
    def depth(self) -> int:
        if self.operator is ProgramOperator.CHANNEL:
            return 0
        if self.right is None:
            assert self.left is not None
            return 1 + self.left.depth
        assert self.left is not None
        return 1 + max(self.left.depth, self.right.depth)

    @property
    def complexity(self) -> int:
        if self.operator is ProgramOperator.CHANNEL:
            return 1
        if self.right is None:
            assert self.left is not None
            return 1 + self.left.complexity
        assert self.left is not None
        return 1 + self.left.complexity + self.right.complexity

    def evaluate(self, channels: tuple[float, ...]) -> float:
        if self.operator is ProgramOperator.CHANNEL:
            assert self.channel_index is not None
            if self.channel_index >= len(channels):
                raise FoundationError("feature program channel is outside observation arity")
            return channels[self.channel_index]
        assert self.left is not None
        left = self.left.evaluate(channels)
        if self.operator is ProgramOperator.ABS:
            return abs(left)
        if self.operator is ProgramOperator.NEGATE:
            return -left
        assert self.right is not None
        right = self.right.evaluate(channels)
        if self.operator is ProgramOperator.ADD:
            return left + right
        if self.operator is ProgramOperator.SUBTRACT:
            return left - right
        if self.operator is ProgramOperator.MULTIPLY:
            return left * right
        raise FoundationError(f"unsupported feature-program operator: {self.operator.value}")

    def expression(self) -> str:
        if self.operator is ProgramOperator.CHANNEL:
            return f"x{self.channel_index}"
        assert self.left is not None
        if self.operator is ProgramOperator.ABS:
            return f"abs({self.left.expression()})"
        if self.operator is ProgramOperator.NEGATE:
            return f"neg({self.left.expression()})"
        assert self.right is not None
        symbol = {
            ProgramOperator.ADD: "+",
            ProgramOperator.SUBTRACT: "-",
            ProgramOperator.MULTIPLY: "*",
        }[self.operator]
        return f"({self.left.expression()}{symbol}{self.right.expression()})"

    def to_payload(self) -> JsonObject:
        return {
            "operator": self.operator.value,
            "channel_index": self.channel_index,
            "left": self.left.to_payload() if self.left is not None else None,
            "right": self.right.to_payload() if self.right is not None else None,
            "depth": self.depth,
            "complexity": self.complexity,
            "expression": self.expression(),
        }


@dataclass(frozen=True, slots=True)
class InventedRepresentationProgram:
    representation_id: str
    program: FeatureProgram
    threshold: float
    polarity: int
    training_accuracy: float
    simple_baseline_accuracy: float
    validation_accuracy: float | None = None

    def __post_init__(self) -> None:
        require_text(self.representation_id, field_name="representation_id")
        if self.polarity not in {-1, 1}:
            raise FoundationError("representation-program polarity must be -1 or 1")
        if not isfinite(self.threshold):
            raise FoundationError("representation-program threshold must be finite")
        if not 0.0 <= self.training_accuracy <= 1.0:
            raise FoundationError("training accuracy must be between zero and one")
        if not 0.0 <= self.simple_baseline_accuracy <= 1.0:
            raise FoundationError("baseline accuracy must be between zero and one")
        if self.validation_accuracy is not None and not 0.0 <= self.validation_accuracy <= 1.0:
            raise FoundationError("validation accuracy must be between zero and one")

    def activates(self, channels: tuple[float, ...]) -> bool:
        value = self.program.evaluate(channels)
        return self.polarity * value >= self.polarity * self.threshold

    def to_payload(self) -> JsonObject:
        return {
            "representation_id": self.representation_id,
            "program": self.program.to_payload(),
            "threshold": self.threshold,
            "polarity": self.polarity,
            "training_accuracy": self.training_accuracy,
            "simple_baseline_accuracy": self.simple_baseline_accuracy,
            "validation_accuracy": self.validation_accuracy,
            "origin": "sally-compositional-representation-invention",
            "human_semantic_label": None,
        }

    def digest(self) -> DigestRecord:
        return DigestRecord.from_payload(self.to_payload())


class RepresentationProgramInventor:
    """Synthesize a multi-operation representation when shallower languages fail."""

    def invent(
        self,
        *,
        observations: Iterable[RepresentationObservation],
        max_depth: int = 2,
        max_candidates: int = 4096,
        minimum_improvement: float = 0.15,
    ) -> InventedRepresentationProgram:
        items = tuple(observations)
        self._validate(items)
        if max_depth < 1 or max_candidates < 1:
            raise FoundationError("representation-program search bounds are invalid")
        if not 0.0 <= minimum_improvement <= 1.0:
            raise FoundationError("minimum improvement must be between zero and one")
        arity = len(items[0].channels)
        levels = self._generate(arity=arity, max_depth=max_depth, max_candidates=max_candidates)
        simple = tuple(program for program in levels if program.depth <= 1)
        all_programs = tuple(levels)
        baseline = self._best(items, simple)
        best = self._best(items, all_programs)
        if baseline is None or best is None:
            raise FoundationError("representation-program search produced no candidate")
        if best[0] < baseline[0] + minimum_improvement:
            raise FoundationError(
                "no compositional representation materially improves shallow features"
            )
        accuracy, program, threshold, polarity = best
        identity = DigestRecord.from_payload(
            {
                "program": program.to_payload(),
                "threshold": threshold,
                "polarity": polarity,
                "training": [item.to_payload() for item in items],
            }
        )
        return InventedRepresentationProgram(
            representation_id=f"program-representation-{identity.value[:16]}",
            program=program,
            threshold=threshold,
            polarity=polarity,
            training_accuracy=accuracy,
            simple_baseline_accuracy=baseline[0],
        )

    def validate(
        self,
        representation: InventedRepresentationProgram,
        *,
        observations: Iterable[RepresentationObservation],
    ) -> InventedRepresentationProgram:
        items = tuple(observations)
        self._validate(items)
        correct = sum(representation.activates(item.channels) is item.consequence for item in items)
        return replace(representation, validation_accuracy=correct / len(items))

    def _generate(
        self, *, arity: int, max_depth: int, max_candidates: int
    ) -> tuple[FeatureProgram, ...]:
        programs: list[FeatureProgram] = [
            FeatureProgram(ProgramOperator.CHANNEL, channel_index=i) for i in range(arity)
        ]
        by_depth: dict[int, list[FeatureProgram]] = {0: list(programs)}
        seen = {program.expression() for program in programs}
        for depth in range(1, max_depth + 1):
            created: list[FeatureProgram] = []
            previous = tuple(program for d in range(depth) for program in by_depth.get(d, ()))
            frontier = tuple(by_depth.get(depth - 1, ()))
            for child in frontier:
                for operator in (ProgramOperator.ABS, ProgramOperator.NEGATE):
                    candidate = FeatureProgram(operator, left=child)
                    if candidate.expression() not in seen:
                        seen.add(candidate.expression())
                        created.append(candidate)
            # At least one child must be from the previous depth so the candidate really grows.
            for left in frontier:
                for right in previous:
                    for operator in (
                        ProgramOperator.ADD,
                        ProgramOperator.SUBTRACT,
                        ProgramOperator.MULTIPLY,
                    ):
                        candidate = FeatureProgram(operator, left=left, right=right)
                        expression = candidate.expression()
                        if expression not in seen:
                            seen.add(expression)
                            created.append(candidate)
                        if len(programs) + len(created) >= max_candidates:
                            break
                    if len(programs) + len(created) >= max_candidates:
                        break
                if len(programs) + len(created) >= max_candidates:
                    break
            by_depth[depth] = created
            programs.extend(created)
            if len(programs) >= max_candidates:
                return tuple(programs[:max_candidates])
            if not created:
                break
        return tuple(programs)

    def _best(
        self,
        observations: tuple[RepresentationObservation, ...],
        programs: tuple[FeatureProgram, ...],
    ) -> tuple[float, FeatureProgram, float, int] | None:
        best: tuple[float, FeatureProgram, float, int] | None = None
        signatures: set[tuple[float, ...]] = set()
        for program in programs:
            values = tuple(round(program.evaluate(item.channels), 12) for item in observations)
            if values in signatures:
                continue
            signatures.add(values)
            for threshold in self._thresholds(values):
                for polarity in (-1, 1):
                    correct = sum(
                        (polarity * value >= polarity * threshold) is item.consequence
                        for value, item in zip(values, observations, strict=True)
                    )
                    accuracy = correct / len(observations)
                    candidate = (accuracy, program, threshold, polarity)
                    if best is None or self._rank(candidate) > self._rank(best):
                        best = candidate
        return best

    @staticmethod
    def _rank(
        item: tuple[float, FeatureProgram, float, int],
    ) -> tuple[float, int, int, float, int, tuple[int, ...]]:
        accuracy, program, threshold, polarity = item
        return (
            accuracy,
            -program.depth,
            -program.complexity,
            -abs(threshold),
            polarity,
            tuple(-ord(ch) for ch in program.expression()),
        )

    @staticmethod
    def _thresholds(values: tuple[float, ...]) -> tuple[float, ...]:
        ordered = sorted(set(values))
        candidates = [ordered[0] - 1.0, ordered[-1] + 1.0, *ordered]
        candidates.extend((left + right) / 2.0 for left, right in itertools.pairwise(ordered))
        return tuple(sorted(set(candidates)))

    @staticmethod
    def _validate(observations: tuple[RepresentationObservation, ...]) -> None:
        if not observations:
            raise FoundationError("representation-program invention requires observations")
        arity = len(observations[0].channels)
        if any(len(item.channels) != arity for item in observations):
            raise FoundationError("representation-program observations must share one arity")
        if len({item.consequence for item in observations}) < 2:
            raise FoundationError(
                "representation-program invention requires both consequence classes"
            )
