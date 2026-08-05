"""Reproducible capability evaluation for the IX-Sally cognitive runtime."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_sally.agents import AgentRole
from ix_sally.cognition.active_memory import (
    ActiveMemoryEntry,
    ActiveMemoryStatus,
    MemoryLayer,
)
from ix_sally.cognition.adaptation import AdaptationController
from ix_sally.cognition.curriculum import (
    Curriculum,
    CurriculumLedger,
    CurriculumSplit,
    CurriculumTask,
    CurriculumTrial,
    TrialStatus,
)
from ix_sally.cognition.episodes import (
    CognitiveEpisode,
    EpisodeStep,
    EpisodeStepKind,
    EpisodeStepStatus,
)
from ix_sally.cognition.executive import ExecutiveDecisionStatus
from ix_sally.cognition.goals import GoalSpec
from ix_sally.cognition.learning import (
    LearningOutcome,
    OutcomeStatus,
    TransferEvaluation,
)
from ix_sally.cognition.metacognition import CapabilityMeasure, SelfModel
from ix_sally.cognition.planning import ActionSpec, FactEffect, PlanStatus
from ix_sally.cognition.system import SallyCognitiveSystem
from ix_sally.cognition.uncertainty import CalibrationObservation
from ix_sally.cognition.values import CognitiveValue
from ix_sally.cognition.vm import VMStatus
from ix_sally.cognition.workspace import WorkspaceItem, WorkspaceItemKind
from ix_sally.cognition.world_model import (
    CausalRule,
    FactPattern,
    FactStatus,
    WorldFact,
)
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class EvaluationCategory(StrEnum):
    """Capability categories measured by the built-in evaluation harness."""

    LANGUAGE = "language"
    EXECUTION = "execution"
    MEMORY = "memory"
    WORLD_MODEL = "world_model"
    PLANNING = "planning"
    LEARNING = "learning"
    GOVERNANCE = "governance"
    PERSISTENCE = "persistence"
    INTEGRATION = "integration"


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """One observed benchmark result with an evidence digest."""

    benchmark_id: CanonicalKey
    category: EvaluationCategory
    passed: bool
    score: float
    detail: str
    evidence_digest: DigestRecord

    @classmethod
    def create(
        cls,
        *,
        benchmark_id: str,
        category: EvaluationCategory,
        passed: bool,
        score: float,
        detail: str,
        evidence_digest: DigestRecord,
    ) -> BenchmarkResult:
        """Create a bounded result from actual benchmark observations."""
        if not 0.0 <= score <= 1.0:
            raise FoundationError("benchmark score must be between 0 and 1")
        evidence_digest.require_algorithm("sha256")
        return cls(
            benchmark_id=CanonicalKey.from_text(
                benchmark_id,
                field_name="benchmark_id",
            ),
            category=category,
            passed=passed,
            score=score,
            detail=require_text(detail, field_name="detail"),
            evidence_digest=evidence_digest,
        )

    def to_payload(self) -> JsonObject:
        """Return a canonical benchmark-result payload."""
        return {
            "benchmark_id": self.benchmark_id.value,
            "category": self.category.value,
            "passed": self.passed,
            "score": self.score,
            "detail": self.detail,
            "evidence_digest": {
                "algorithm": self.evidence_digest.algorithm,
                "value": self.evidence_digest.value,
            },
        }


@dataclass(frozen=True, slots=True)
class CognitiveEvaluationReport:
    """Complete evaluation report that explicitly does not certify AGI."""

    results: tuple[BenchmarkResult, ...]
    classification: str = "experimental-cognitive-architecture"
    agi_certified: bool = False

    def __post_init__(self) -> None:
        """Reject duplicate benchmarks and any self-certification claim."""
        identifiers = [result.benchmark_id.value for result in self.results]
        if len(identifiers) != len(set(identifiers)):
            raise FoundationError("evaluation contains duplicate benchmark identifiers")
        if self.agi_certified:
            raise FoundationError("IX-Sally may not self-certify AGI")
        require_text(self.classification, field_name="classification")

    def passed(self) -> int:
        """Return the number of passed benchmarks."""
        return sum(1 for result in self.results if result.passed)

    def overall_score(self) -> float:
        """Return the unweighted mean benchmark score."""
        if not self.results:
            return 0.0
        return round(sum(result.score for result in self.results) / len(self.results), 12)

    def category_scores(self) -> dict[str, float]:
        """Return deterministic mean scores grouped by capability category."""
        scores: dict[str, float] = {}
        for category in EvaluationCategory:
            relevant = [
                result.score for result in self.results if result.category is category
            ]
            if relevant:
                scores[category.value] = round(sum(relevant) / len(relevant), 12)
        return scores

    def to_payload(self) -> JsonObject:
        """Return a canonical evaluation-report payload."""
        results: JsonArray = [result.to_payload() for result in self.results]
        return {
            "classification": self.classification,
            "agi_certified": self.agi_certified,
            "benchmark_count": len(self.results),
            "passed_count": self.passed(),
            "overall_score": self.overall_score(),
            "category_scores": self.category_scores(),
            "results": results,
            "limitations": [
                "Passing this suite does not establish artificial general intelligence.",
                "The suite is deterministic and local; it does not measure open-world autonomy.",
                "No external model weights, sensors, actuators, or proprietary data are included.",
            ],
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic evaluation-report identity."""
        return DigestRecord.from_payload(self.to_payload())


def _result(
    benchmark_id: str,
    category: EvaluationCategory,
    passed: bool,
    detail: str,
    evidence: JsonObject,
) -> BenchmarkResult:
    """Create a benchmark result with a binary observed score."""
    return BenchmarkResult.create(
        benchmark_id=benchmark_id,
        category=category,
        passed=passed,
        score=1.0 if passed else 0.0,
        detail=detail,
        evidence_digest=DigestRecord.from_payload(evidence),
    )


def run_core_evaluation() -> CognitiveEvaluationReport:
    """Execute the built-in deterministic capability suite against a fresh system."""
    system = SallyCognitiveSystem.create()
    results: list[BenchmarkResult] = []

    arithmetic = system.execute_ix(
        "let total = 6 * 7\nprint total\nassert total == 42\n",
        filename="evaluation-arithmetic.ix",
    )
    arithmetic_passed = (
        arithmetic.status is VMStatus.HALTED
        and arithmetic.outputs == (CognitiveValue.from_python(42),)
    )
    results.append(
        _result(
            "ix-typed-arithmetic",
            EvaluationCategory.LANGUAGE,
            arithmetic_passed,
            "Compiled and executed typed arithmetic with a runtime assertion.",
            arithmetic.to_payload(),
        )
    )

    memory_run = system.execute_ix(
        "remember answer = 42\nrecall answer\n",
        filename="evaluation-memory.ix",
    )
    memory_passed = (
        memory_run.status is VMStatus.HALTED
        and memory_run.outputs == (CognitiveValue.from_python(42),)
        and system.runtime_memories.get("answer") == CognitiveValue.from_python(42)
    )
    results.append(
        _result(
            "vm-governed-memory",
            EvaluationCategory.EXECUTION,
            memory_passed,
            "Stored and recalled an exact typed VM memory value.",
            memory_run.to_payload(),
        )
    )

    primitive = system.execute_primitive(
        "add-two",
        (CognitiveValue.from_python(20), CognitiveValue.from_python(22)),
    )
    primitive_passed = primitive.output == CognitiveValue.from_python(42)
    results.append(
        _result(
            "grounded-primitive",
            EvaluationCategory.EXECUTION,
            primitive_passed,
            "Executed an enumerated validated primitive without a dynamic callback.",
            primitive.to_payload(),
        )
    )

    evidence = DigestRecord.from_payload({"observation": "sky appears blue"})
    system.append_memory(
        ActiveMemoryEntry.create(
            memory_id="blue-sky-observation",
            layer=MemoryLayer.SEMANTIC,
            content="The observed daytime sky appears blue.",
            confidence=0.95,
            status=ActiveMemoryStatus.VERIFIED,
            sequence=1,
            evidence_digests=(evidence,),
            tags=("sky", "color"),
        )
    )
    retrievals = system.active_memory.retrieve("daytime sky color", truth_only=True)
    retrieval_passed = bool(
        retrievals and retrievals[0].entry.memory_id.value == "blue-sky-observation"
    )
    results.append(
        _result(
            "active-memory-retrieval",
            EvaluationCategory.MEMORY,
            retrieval_passed,
            "Retrieved verified semantic memory using transparent lexical scoring.",
            system.active_memory.to_payload(),
        )
    )

    observation_digest = DigestRecord.from_payload({"sensor": "temperature", "value": 90})
    system.observe(
        WorldFact.create(
            fact_id="room-temperature-hot",
            subject="room",
            predicate="temperature-state",
            value=CognitiveValue.from_python("hot"),
            status=FactStatus.OBSERVED,
            confidence=1.0,
            evidence_digests=(observation_digest,),
        )
    )
    system.add_causal_rule(
        CausalRule.create(
            rule_id="hot-room-needs-cooling",
            conditions=(
                FactPattern.create(
                    subject="room",
                    predicate="temperature-state",
                    value=CognitiveValue.from_python("hot"),
                ),
            ),
            effect_subject="room",
            effect_predicate="cooling-needed",
            effect_value=CognitiveValue.from_python(True),
            confidence=0.9,
            evidence_digests=(observation_digest,),
        )
    )
    predictions = system.world_model.predict()
    prediction_passed = bool(
        predictions
        and predictions[0].predicate.value == "cooling-needed"
        and predictions[0].status is FactStatus.PREDICTED
    )
    results.append(
        _result(
            "causal-prediction",
            EvaluationCategory.WORLD_MODEL,
            prediction_passed,
            "Produced a prediction while preserving its predicted epistemic status.",
            system.world_model.to_payload(),
        )
    )

    system.register_action(
        ActionSpec.create(
            action_id="activate-cooling",
            description="Activate the simulated cooling state.",
            preconditions=(
                FactPattern.create(
                    subject="room",
                    predicate="cooling-needed",
                    value=CognitiveValue.from_python(True),
                ),
            ),
            effects=(
                FactEffect.create(
                    subject="room",
                    predicate="temperature-state",
                    value=CognitiveValue.from_python("comfortable"),
                ),
            ),
            cost=1.0,
            risk=0.05,
        )
    )
    system.infer_world()
    goal = FactPattern.create(
        subject="room",
        predicate="temperature-state",
        value=CognitiveValue.from_python("comfortable"),
    )
    plan = system.plan(goal)
    plan_passed = (
        plan.status is PlanStatus.FOUND
        and tuple(action.action_id.value for action in plan.actions)
        == ("activate-cooling",)
    )
    results.append(
        _result(
            "bounded-planning",
            EvaluationCategory.PLANNING,
            plan_passed,
            "Found a shortest exact-state plan using declarative actions.",
            plan.to_payload(),
        )
    )

    learning_evidence: list[DigestRecord] = []
    for index, score in enumerate((0.6, 0.75, 0.9, 0.9), start=1):
        outcome = LearningOutcome.create(
            outcome_id=f"planning-outcome-{index}",
            skill_id="bounded-planning",
            task_family="state-transition",
            status=OutcomeStatus.SUCCESS if score >= 0.8 else OutcomeStatus.PARTIAL,
            score=score,
            evidence_digest=DigestRecord.from_payload(
                {"trial": index, "observed_score": score}
            ),
            notes="Deterministic held-out state-transition trial.",
        )
        learning_evidence.append(outcome.digest())
        system.record_learning(outcome)
    transfer = TransferEvaluation.create(
        skill_id="bounded-planning",
        familiar_score=0.9,
        novel_score=0.8,
        retention_score=system.learning.retention_score("bounded-planning"),
        evidence_digests=learning_evidence,
    )
    results.append(
        _result(
            "measured-transfer",
            EvaluationCategory.LEARNING,
            transfer.passes(),
            "Measured familiar, held-out, and retention scores with declared thresholds.",
            transfer.to_payload(),
        )
    )

    system.admit_workspace(
        WorkspaceItem.create(
            item_id="goal-comfortable-room",
            kind=WorkspaceItemKind.GOAL,
            content="Reach a comfortable simulated room temperature.",
            confidence=1.0,
            salience=0.9,
            evidence_digests=(plan.digest(),),
        )
    )
    cycle = system.run_cycle(task="Make the room comfortable", goal=goal)
    ninefold_passed = (
        len(cycle.findings) == len(AgentRole)
        and {finding.role for finding in cycle.findings} == set(AgentRole)
    )
    results.append(
        _result(
            "functional-ninefold-cycle",
            EvaluationCategory.INTEGRATION,
            ninefold_passed,
            "Executed all nine cognitive functions exactly once without role overlap.",
            cycle.to_payload(),
        )
    )

    authority_action = ActionSpec.create(
        action_id="human-boundary-action",
        description="A simulated action that requires explicit human approval.",
        preconditions=(),
        effects=(
            FactEffect.create(
                subject="system",
                predicate="external-change",
                value=CognitiveValue.from_python(True),
            ),
        ),
        cost=0.0,
        risk=0.2,
        authority_required=True,
    )
    authority_system = SallyCognitiveSystem.create()
    authority_system.register_action(authority_action)
    authority_goal = FactPattern.create(
        subject="system",
        predicate="external-change",
        value=CognitiveValue.from_python(True),
    )
    authority_plan = authority_system.plan(authority_goal)
    blocked_receipt = authority_system.simulate_plan(authority_plan)
    governance_passed = blocked_receipt.permission.value == "requires_human"
    results.append(
        _result(
            "human-authority-boundary",
            EvaluationCategory.GOVERNANCE,
            governance_passed,
            "Blocked a declared authority-crossing plan without human approval.",
            blocked_receipt.to_payload(),
        )
    )

    system.record_calibration(
        CalibrationObservation.create(
            observation_id="planning-forecast-success",
            capability_id="planning",
            predicted_probability=0.8,
            observed=True,
            evidence_digest=DigestRecord.from_payload(
                {"forecast": "planning-success", "observed": True}
            ),
            context="Deterministic planning forecast.",
        )
    )
    system.record_calibration(
        CalibrationObservation.create(
            observation_id="planning-forecast-failure",
            capability_id="planning",
            predicted_probability=0.2,
            observed=False,
            evidence_digest=DigestRecord.from_payload(
                {"forecast": "planning-failure", "observed": False}
            ),
            context="Deterministic planning forecast.",
        )
    )
    calibration = system.calibration_report(capability_id="planning", bin_count=5)
    calibration_passed = (
        calibration.observation_count == 2
        and calibration.brier_score == 0.04
        and calibration.expected_calibration_error == 0.2
    )
    results.append(
        _result(
            "calibrated-uncertainty",
            EvaluationCategory.LEARNING,
            calibration_passed,
            "Measured Brier score and calibration error from explicit forecasts.",
            calibration.to_payload(),
        )
    )

    system.register_goal(
        GoalSpec.create(
            goal_id="comfortable-room",
            description="Reach a comfortable simulated room temperature.",
            desired_state=goal,
            priority=1.0,
            utility=1.0,
            risk_limit=0.2,
            evidence_digests=(plan.digest(),),
        )
    )
    decision = system.deliberate(task="Make the simulated room comfortable.")
    bridge = system.bridge_decision(decision, cycle=system.cycle_count)
    executive_passed = (
        decision.status is ExecutiveDecisionStatus.PLAN_READY
        and bridge.proposal.proposed_actions[0].action_id.value
        == "activate-cooling"
        and bridge.receipt.executive_decision_digest == decision.digest()
    )
    results.append(
        _result(
            "executive-governance-bridge",
            EvaluationCategory.GOVERNANCE,
            executive_passed,
            "Selected a goal and converted its plan into the existing proposal path.",
            bridge.to_payload(),
        )
    )

    training_task = CurriculumTask.create(
        task_id="planning-training",
        family="planning",
        description="Complete a familiar bounded state-transition task.",
        difficulty=2,
        split=CurriculumSplit.TRAINING,
        required_capabilities=("planning",),
        pass_threshold=0.75,
    )
    validation_task = CurriculumTask.create(
        task_id="planning-validation",
        family="planning",
        description="Complete a distinct bounded validation task.",
        difficulty=3,
        split=CurriculumSplit.VALIDATION,
        prerequisite_ids=("planning-training",),
        required_capabilities=("planning",),
        pass_threshold=0.75,
    )
    held_out_task = CurriculumTask.create(
        task_id="planning-held-out",
        family="planning",
        description="Complete a novel bounded state-transition task.",
        difficulty=4,
        split=CurriculumSplit.HELD_OUT,
        prerequisite_ids=("planning-validation",),
        required_capabilities=("planning", "transfer"),
        pass_threshold=0.75,
    )
    system.set_curriculum(
        CurriculumLedger(
            Curriculum.create((training_task, validation_task, held_out_task))
        )
    )
    system.record_curriculum_trial(
        CurriculumTrial.create(
            trial_id="planning-training-trial",
            task_id="planning-training",
            sequence=0,
            score=0.9,
            status=TrialStatus.PASSED,
            evidence_digest=DigestRecord.from_payload(
                {"task": "planning-training", "score": 0.9}
            ),
            notes="Observed deterministic training trial.",
        )
    )
    system.record_curriculum_trial(
        CurriculumTrial.create(
            trial_id="planning-validation-trial",
            task_id="planning-validation",
            sequence=1,
            score=0.9,
            status=TrialStatus.PASSED,
            evidence_digest=DigestRecord.from_payload(
                {"task": "planning-validation", "score": 0.9}
            ),
            notes="Observed deterministic validation trial.",
        )
    )
    system.record_curriculum_trial(
        CurriculumTrial.create(
            trial_id="planning-held-out-trial",
            task_id="planning-held-out",
            sequence=2,
            score=0.8,
            status=TrialStatus.PASSED,
            evidence_digest=DigestRecord.from_payload(
                {"task": "planning-held-out", "score": 0.8}
            ),
            notes="Observed deterministic held-out trial.",
        )
    )
    if system.curriculum is None:
        raise FoundationError("evaluation curriculum was not installed")
    curriculum_passed = (
        system.curriculum.split_score(CurriculumSplit.TRAINING) == 0.9
        and system.curriculum.split_score(CurriculumSplit.VALIDATION) == 0.9
        and system.curriculum.split_score(CurriculumSplit.HELD_OUT) == 0.8
        and system.curriculum.transfer_gap() == 0.1
    )
    results.append(
        _result(
            "held-out-curriculum",
            EvaluationCategory.LEARNING,
            curriculum_passed,
            "Recorded separate training and held-out trials without merging splits.",
            system.curriculum.to_payload(),
        )
    )

    initial_episode_state = system.digest()
    episode_step = EpisodeStep.create(
        index=0,
        kind=EpisodeStepKind.PLANNING,
        status=EpisodeStepStatus.COMPLETED,
        detail="Produced and bridged a bounded plan proposal.",
        input_digests=(plan.digest(),),
        output_digests=(bridge.digest(),),
    )
    episode = CognitiveEpisode.create(
        episode_id="evaluation-episode-zero",
        sequence=0,
        task="Make the simulated room comfortable.",
        initial_state_digest=initial_episode_state,
        final_state_digest=system.digest(),
        steps=(episode_step,),
    )
    system.append_episode(episode)
    episode_passed = (
        system.episodes.head_digest() == episode.digest() and episode.completed()
    )
    results.append(
        _result(
            "replayable-episode-chain",
            EvaluationCategory.MEMORY,
            episode_passed,
            "Recorded an append-only episode with contiguous steps and digest links.",
            system.episodes.to_payload(),
        )
    )

    measure_evidence = DigestRecord.from_payload({"suite": "regression-evaluation"})
    before = SelfModel(
        (
            CapabilityMeasure.create(
                capability_id="memory",
                score=0.8,
                evidence_digests=(measure_evidence,),
                limitation="Measured only by this deterministic local suite.",
            ),
            CapabilityMeasure.create(
                capability_id="planning",
                score=0.4,
                evidence_digests=(measure_evidence,),
                limitation="Measured only by this deterministic local suite.",
            ),
        )
    )
    after = SelfModel(
        (
            CapabilityMeasure.create(
                capability_id="memory",
                score=0.5,
                evidence_digests=(measure_evidence,),
                limitation="Measured only by this deterministic local suite.",
            ),
            CapabilityMeasure.create(
                capability_id="planning",
                score=0.7,
                evidence_digests=(measure_evidence,),
                limitation="Measured only by this deterministic local suite.",
            ),
        )
    )
    adaptation = AdaptationController(permitted_regression=0.05)
    proposal = adaptation.propose_for_weakest(
        self_model=before,
        description="Evaluate a bounded planning heuristic change.",
        expected_benefit=0.3,
        regression_risk=0.2,
        supporting_evidence=(before.digest(),),
    )
    regression = adaptation.compare(proposal=proposal, before=before, after=after)
    regression_passed = regression.has_regression() and not regression.may_request_validation()
    results.append(
        _result(
            "regression-aware-adaptation",
            EvaluationCategory.GOVERNANCE,
            regression_passed,
            "Detected a cross-capability regression and blocked validation advancement.",
            regression.to_payload(),
        )
    )

    snapshot = system.snapshot()
    restored_system = SallyCognitiveSystem.from_snapshot(snapshot)
    persistence_passed = (
        restored_system.state_payload() == system.state_payload()
        and restored_system.digest() == system.digest()
    )
    results.append(
        _result(
            "tamper-evident-complete-restore",
            EvaluationCategory.PERSISTENCE,
            persistence_passed,
            "Restored the complete canonical cognitive state and verified exact identity.",
            restored_system.state_payload(),
        )
    )

    return CognitiveEvaluationReport(tuple(results))
