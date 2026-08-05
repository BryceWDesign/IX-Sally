"""Bounded executive selection, planning, risk gating, and decision receipts."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.cognition.active_memory import ActiveMemoryStore
from ix_sally.cognition.goals import GoalGraph, GoalSpec
from ix_sally.cognition.planning import ActionSpec, DeterministicPlanner, Plan, PlanStatus
from ix_sally.cognition.uncertainty import CalibrationReport
from ix_sally.cognition.workspace import CognitiveWorkspace, WorkspaceItemKind
from ix_sally.cognition.world_model import WorldModel
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class ExecutiveDecisionStatus(StrEnum):
    """Outcome of one bounded executive deliberation."""

    NO_SELECTABLE_GOAL = "no_selectable_goal"
    GOAL_SATISFIED = "goal_satisfied"
    PLAN_READY = "plan_ready"
    REQUIRES_HUMAN = "requires_human"
    BLOCKED_RISK = "blocked_risk"
    BLOCKED_UNCERTAINTY = "blocked_uncertainty"
    PLAN_NOT_FOUND = "plan_not_found"


@dataclass(frozen=True, slots=True)
class ExecutiveDecision:
    """One deterministic decision that proposes rather than executes a plan."""

    decision_id: CanonicalKey
    status: ExecutiveDecisionStatus
    task: str
    selected_goal: GoalSpec | None
    plan: Plan | None
    blockers: tuple[str, ...]
    confidence: float
    evidence_digests: tuple[DigestRecord, ...]
    rationale: str

    @classmethod
    def create(
        cls,
        *,
        task: str,
        status: ExecutiveDecisionStatus,
        selected_goal: GoalSpec | None,
        plan: Plan | None,
        blockers: Iterable[str],
        confidence: float,
        evidence_digests: Iterable[DigestRecord],
        rationale: str,
    ) -> ExecutiveDecision:
        """Create a decision with coherent status and evidence references."""
        if not 0.0 <= confidence <= 1.0:
            raise FoundationError("executive confidence must be between 0 and 1")
        normalized_blockers = tuple(
            require_text(item, field_name="blocker") for item in blockers
        )
        evidence = tuple(evidence_digests)
        if not evidence:
            raise FoundationError("executive decision requires evidence digests")
        for digest in evidence:
            digest.require_algorithm("sha256")
        if status in {
            ExecutiveDecisionStatus.PLAN_READY,
            ExecutiveDecisionStatus.REQUIRES_HUMAN,
            ExecutiveDecisionStatus.BLOCKED_RISK,
        } and plan is None:
            raise FoundationError(f"{status.value} executive decision requires a plan")
        if status is ExecutiveDecisionStatus.PLAN_NOT_FOUND:
            if plan is None or plan.status not in {
                PlanStatus.NOT_FOUND,
                PlanStatus.SEARCH_LIMIT,
            }:
                raise FoundationError("plan-not-found decision requires a failed plan")
        if status is ExecutiveDecisionStatus.NO_SELECTABLE_GOAL and selected_goal is not None:
            raise FoundationError("no-selectable-goal decision must not select a goal")
        seed = DigestRecord.from_payload(
            {
                "task": task,
                "status": status.value,
                "goal": (
                    selected_goal.goal_id.value if selected_goal is not None else None
                ),
                "plan": plan.digest().value if plan is not None else None,
                "evidence": [item.value for item in evidence],
            }
        )
        return cls(
            decision_id=CanonicalKey.from_text(
                f"executive-decision-{seed.value[:24]}",
                field_name="decision_id",
            ),
            status=status,
            task=require_text(task, field_name="task"),
            selected_goal=selected_goal,
            plan=plan,
            blockers=normalized_blockers,
            confidence=confidence,
            evidence_digests=evidence,
            rationale=require_text(rationale, field_name="rationale"),
        )

    def may_enter_governance(self) -> bool:
        """Return whether this proposal may proceed to the authority control plane."""
        return self.status in {
            ExecutiveDecisionStatus.PLAN_READY,
            ExecutiveDecisionStatus.REQUIRES_HUMAN,
        }

    def to_payload(self) -> JsonObject:
        """Return a canonical executive-decision payload."""
        evidence: JsonArray = [
            {"algorithm": item.algorithm, "value": item.value}
            for item in self.evidence_digests
        ]
        blockers: JsonArray = list(self.blockers)
        return {
            "decision_id": self.decision_id.value,
            "status": self.status.value,
            "task": self.task,
            "selected_goal": (
                self.selected_goal.to_payload()
                if self.selected_goal is not None
                else None
            ),
            "plan": self.plan.to_payload() if self.plan is not None else None,
            "blockers": blockers,
            "confidence": self.confidence,
            "evidence_digests": evidence,
            "rationale": self.rationale,
            "may_enter_governance": self.may_enter_governance(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic decision identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ExecutiveController:
    """Select one goal and produce a bounded plan proposal under explicit gates."""

    planner: DeterministicPlanner = DeterministicPlanner()
    maximum_calibration_error: float = 0.25

    def __post_init__(self) -> None:
        """Require a valid uncertainty gate."""
        if not 0.0 <= self.maximum_calibration_error <= 1.0:
            raise FoundationError(
                "maximum calibration error must be between 0 and 1"
            )

    def deliberate(
        self,
        *,
        task: str,
        goals: GoalGraph,
        workspace: CognitiveWorkspace,
        memory: ActiveMemoryStore,
        world_model: WorldModel,
        actions: Iterable[ActionSpec],
        calibration: CalibrationReport | None = None,
    ) -> ExecutiveDecision:
        """Select and plan without executing or granting authority."""
        normalized_task = require_text(task, field_name="task")
        reconciled = goals.reconcile(world_model)
        selected = reconciled.select(world_model)
        base_evidence = (
            reconciled.digest(),
            workspace.digest(),
            memory.digest(),
            world_model.digest(),
        )
        if selected is None:
            satisfied = tuple(
                goal for goal in reconciled.goals if goal.status.value == "satisfied"
            )
            status = (
                ExecutiveDecisionStatus.GOAL_SATISFIED
                if satisfied
                else ExecutiveDecisionStatus.NO_SELECTABLE_GOAL
            )
            return ExecutiveDecision.create(
                task=normalized_task,
                status=status,
                selected_goal=None,
                plan=None,
                blockers=(),
                confidence=1.0 if satisfied else 0.0,
                evidence_digests=base_evidence,
                rationale=(
                    "All currently eligible goals are already satisfied."
                    if satisfied
                    else "No goal currently satisfies dependency and lifecycle gates."
                ),
            )
        if calibration is not None:
            evidence = (*base_evidence, calibration.digest())
            if (
                calibration.observation_count > 0
                and calibration.expected_calibration_error
                > self.maximum_calibration_error
            ):
                return ExecutiveDecision.create(
                    task=normalized_task,
                    status=ExecutiveDecisionStatus.BLOCKED_UNCERTAINTY,
                    selected_goal=selected,
                    plan=None,
                    blockers=(
                        "Calibration error exceeds the configured executive threshold.",
                    ),
                    confidence=max(
                        0.0,
                        1.0 - calibration.expected_calibration_error,
                    ),
                    evidence_digests=evidence,
                    rationale="Planning was withheld because confidence is miscalibrated.",
                )
        else:
            evidence = base_evidence
        plan = self.planner.plan(
            world_model=world_model,
            actions=tuple(actions),
            goal=selected.desired_state,
        )
        evidence = (*evidence, plan.digest())
        if plan.status in {PlanStatus.NOT_FOUND, PlanStatus.SEARCH_LIMIT}:
            return ExecutiveDecision.create(
                task=normalized_task,
                status=ExecutiveDecisionStatus.PLAN_NOT_FOUND,
                selected_goal=selected,
                plan=plan,
                blockers=(plan.reason,),
                confidence=0.0,
                evidence_digests=evidence,
                rationale="The bounded planner did not establish an executable path.",
            )
        if plan.status is PlanStatus.ALREADY_SATISFIED:
            return ExecutiveDecision.create(
                task=normalized_task,
                status=ExecutiveDecisionStatus.GOAL_SATISFIED,
                selected_goal=selected,
                plan=None,
                blockers=(),
                confidence=1.0,
                evidence_digests=evidence,
                rationale="The selected goal is already satisfied by current world state.",
            )
        explicit_risks = tuple(
            item for item in workspace.items if item.kind is WorkspaceItemKind.RISK
        )
        if plan.aggregate_risk > selected.risk_limit:
            return ExecutiveDecision.create(
                task=normalized_task,
                status=ExecutiveDecisionStatus.BLOCKED_RISK,
                selected_goal=selected,
                plan=plan,
                blockers=(
                    "Plan aggregate risk exceeds the selected goal risk limit.",
                    *(item.content for item in explicit_risks),
                ),
                confidence=max(0.0, 1.0 - plan.aggregate_risk),
                evidence_digests=evidence,
                rationale="The plan is withheld because its declared risk is too high.",
            )
        requires_human = selected.authority_required or plan.requires_human_authority()
        return ExecutiveDecision.create(
            task=normalized_task,
            status=(
                ExecutiveDecisionStatus.REQUIRES_HUMAN
                if requires_human
                else ExecutiveDecisionStatus.PLAN_READY
            ),
            selected_goal=selected,
            plan=plan,
            blockers=(
                ("Explicit human authority is required before execution.",)
                if requires_human
                else ()
            ),
            confidence=max(0.0, 1.0 - plan.aggregate_risk),
            evidence_digests=evidence,
            rationale=(
                "A bounded plan is ready for human authority review."
                if requires_human
                else "A bounded plan is ready to enter the existing governance pipeline."
            ),
        )
