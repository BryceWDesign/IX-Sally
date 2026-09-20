"""Open-ended internal goal genesis for IX-Sally.

Unlike InstrumentalGoalGenerator, this module has no fixed enum of goal kinds.  Sally
explores reachable counterfactual states inside a bounded cognitive sandbox and may turn
one of those states into a new goal based on intrinsic novelty, information value,
competence expansion, simplicity, reversibility, and risk.

Goal content is therefore generated at runtime rather than selected from a prewritten
catalog.  This grants internal goal authorship, not unilateral external authority.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable

from ix_sally.cognition.goals import GoalSpec, GoalStatus
from ix_sally.cognition.open_choice import ActionPrimitive
from ix_sally.cognition.values import CognitiveValue
from ix_sally.cognition.world_model import FactPattern
from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import FoundationError


@dataclass(frozen=True, slots=True)
class IntrinsicDrives:
    """Stable values used to choose among self-generated goal candidates."""

    novelty: float = 0.35
    information_gain: float = 0.25
    competence_expansion: float = 0.20
    simplicity: float = 0.15
    reversibility: float = 0.05
    risk_penalty: float = 0.30

    def __post_init__(self) -> None:
        for name, value in (
            ("novelty", self.novelty),
            ("information_gain", self.information_gain),
            ("competence_expansion", self.competence_expansion),
            ("simplicity", self.simplicity),
            ("reversibility", self.reversibility),
            ("risk_penalty", self.risk_penalty),
        ):
            if not 0.0 <= value <= 1.0:
                raise FoundationError(f"{name} must be between zero and one")


@dataclass(frozen=True, slots=True)
class GeneratedGoal:
    """A goal whose target state and identity were authored during deliberation."""

    goal: GoalSpec
    initial_state: int
    target_state: int
    generating_program: tuple[str, ...]
    intrinsic_score: float
    novelty: float
    information_gain: float
    competence_expansion: float
    simplicity: float
    reversibility: float
    risk: float
    origin: str = "sally-open-goal-genesis"

    def to_payload(self) -> JsonObject:
        return {
            "goal": self.goal.to_payload(),
            "initial_state": self.initial_state,
            "target_state": self.target_state,
            "generating_program": list(self.generating_program),
            "intrinsic_score": self.intrinsic_score,
            "novelty": self.novelty,
            "information_gain": self.information_gain,
            "competence_expansion": self.competence_expansion,
            "simplicity": self.simplicity,
            "reversibility": self.reversibility,
            "risk": self.risk,
            "origin": self.origin,
            "external_authority_granted": False,
        }

    def digest(self) -> DigestRecord:
        return DigestRecord.from_payload(self.to_payload())


class OpenGoalGenesis:
    """Invent new sandbox goals from reachable possibilities instead of a goal catalog."""

    def generate(
        self,
        *,
        initial_state: int,
        primitives: Iterable[ActionPrimitive],
        known_states: Iterable[int] = (),
        drives: IntrinsicDrives | None = None,
        max_depth: int = 4,
        max_programs: int = 512,
        state_bound: int = 256,
    ) -> GeneratedGoal:
        """Construct and select a new internal target without receiving a target value."""
        primitive_tuple = tuple(primitives)
        if not primitive_tuple:
            raise FoundationError("open goal genesis requires action primitives")
        if max_depth < 1 or max_programs < 1 or state_bound < 1:
            raise FoundationError("goal genesis bounds must be positive")
        identifiers = tuple(item.primitive_id for item in primitive_tuple)
        if len(identifiers) != len(set(identifiers)):
            raise FoundationError("goal genesis primitive identifiers must be unique")

        values = drives or IntrinsicDrives()
        known = set(known_states)
        known.add(initial_state)
        queue: deque[tuple[int, tuple[str, ...]]] = deque([(initial_state, ())])
        explored = 0
        candidates: list[GeneratedGoal] = []

        while queue and explored < max_programs:
            state, program = queue.popleft()
            if len(program) >= max_depth:
                continue
            for primitive in primitive_tuple:
                next_state = primitive.apply(state)
                explored += 1
                next_program = (*program, primitive.primitive_id)
                if abs(next_state) > state_bound:
                    if explored >= max_programs:
                        break
                    continue
                proposal = self._candidate(
                    initial_state=initial_state,
                    target_state=next_state,
                    program=next_program,
                    primitives=primitive_tuple,
                    known_states=known,
                    drives=values,
                    state_bound=state_bound,
                )
                if next_state != initial_state:
                    candidates.append(proposal)
                queue.append((next_state, next_program))
                if explored >= max_programs:
                    break

        if not candidates:
            raise FoundationError("open goal genesis found no admissible target")
        return max(
            candidates,
            key=lambda item: (
                item.intrinsic_score,
                item.novelty,
                item.information_gain,
                item.competence_expansion,
                item.simplicity,
                -item.risk,
                tuple(-ord(ch) for ch in ">".join(item.generating_program)),
                -item.target_state,
            ),
        )

    def _candidate(
        self,
        *,
        initial_state: int,
        target_state: int,
        program: tuple[str, ...],
        primitives: tuple[ActionPrimitive, ...],
        known_states: set[int],
        drives: IntrinsicDrives,
        state_bound: int,
    ) -> GeneratedGoal:
        novelty = 0.0 if target_state in known_states else 1.0
        information_gain = novelty / len(program)
        competence = len(set(program)) / len(primitives)
        simplicity = 1.0 / len(program)
        reversible = any(item.apply(target_state) == initial_state for item in primitives)
        reversibility = 1.0 if reversible else 0.0
        risk = min(1.0, abs(target_state - initial_state) / state_bound)
        score = (
            drives.novelty * novelty
            + drives.information_gain * information_gain
            + drives.competence_expansion * competence
            + drives.simplicity * simplicity
            + drives.reversibility * reversibility
            - drives.risk_penalty * risk
        )
        identity = DigestRecord.from_payload(
            {
                "initial_state": initial_state,
                "target_state": target_state,
                "program": list(program),
                "score": round(score, 12),
            }
        )
        goal = GoalSpec.create(
            goal_id=f"self-goal-{identity.value[:16]}",
            description=(
                "Self-generated internal objective: investigate and, if still useful, reach "
                f"sandbox state {target_state} via a newly selected counterfactual path."
            ),
            desired_state=FactPattern.create(
                subject="cognitive-sandbox",
                predicate="state-value",
                value=CognitiveValue.from_python(target_state),
            ),
            priority=round(min(1.0, max(0.0, 0.45 + score * 0.35)), 6),
            utility=round(min(1.0, max(0.0, 0.50 + score * 0.30)), 6),
            risk_limit=0.25,
            status=GoalStatus.PROPOSED,
            authority_required=False,
            evidence_digests=(identity,),
        )
        return GeneratedGoal(
            goal=goal,
            initial_state=initial_state,
            target_state=target_state,
            generating_program=program,
            intrinsic_score=round(score, 12),
            novelty=novelty,
            information_gain=information_gain,
            competence_expansion=competence,
            simplicity=simplicity,
            reversibility=reversibility,
            risk=risk,
        )
