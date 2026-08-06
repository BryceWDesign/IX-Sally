"""Executive deliberation, cognitive governance bridge, and adaptation tests."""

from __future__ import annotations

import pytest

from ix_sally.claims import ClaimStatus
from ix_sally.cognition import (
    ActionSpec,
    CognitiveValue,
    CognitiveWorkspace,
    FactEffect,
    FactPattern,
    FactStatus,
    WorkspaceItem,
    WorkspaceItemKind,
    WorldFact,
    WorldModel,
)
from ix_sally.cognition.active_memory import ActiveMemoryStore
from ix_sally.cognition.adaptation import AdaptationController, RegressionOutcome
from ix_sally.cognition.executive import ExecutiveController, ExecutiveDecisionStatus
from ix_sally.cognition.goals import GoalGraph, GoalSpec
from ix_sally.cognition.governance_bridge import CognitiveProposalBridge
from ix_sally.cognition.metacognition import CapabilityMeasure, ImprovementStatus, SelfModel
from ix_sally.cognition.uncertainty import CalibrationObservation, UncertaintyLedger
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError


def _digest(name: str) -> DigestRecord:
    return DigestRecord.from_payload({"evidence": name})


def _pattern(value: str) -> FactPattern:
    return FactPattern.create(
        subject="machine",
        predicate="state",
        value=CognitiveValue.from_python(value),
    )


def _goal(*, risk_limit: float = 0.3, authority_required: bool = False) -> GoalSpec:
    return GoalSpec.create(
        goal_id="machine-ready",
        description="Move the simulated machine to ready state.",
        desired_state=_pattern("ready"),
        priority=1.0,
        utility=1.0,
        risk_limit=risk_limit,
        authority_required=authority_required,
    )


def _model() -> WorldModel:
    return WorldModel(
        (
            WorldFact.create(
                fact_id="machine-off",
                subject="machine",
                predicate="state",
                value=CognitiveValue.from_python("off"),
                status=FactStatus.OBSERVED,
                confidence=1.0,
                evidence_digests=(_digest("machine-off"),),
            ),
        ),
        (),
    )


def _action(*, risk: float = 0.1, authority_required: bool = False) -> ActionSpec:
    return ActionSpec.create(
        action_id="prepare-machine",
        description="Prepare the simulated machine.",
        preconditions=(_pattern("off"),),
        effects=(
            FactEffect.create(
                subject="machine",
                predicate="state",
                value=CognitiveValue.from_python("ready"),
            ),
        ),
        cost=1.0,
        risk=risk,
        authority_required=authority_required,
    )


def _controller_decision(
    *,
    goal: GoalSpec | None = None,
    action: ActionSpec | None = None,
    workspace: CognitiveWorkspace | None = None,
    uncertainty: UncertaintyLedger | None = None,
):
    calibration = uncertainty.report() if uncertainty is not None else None
    return ExecutiveController().deliberate(
        task="Prepare the machine.",
        goals=GoalGraph.create((goal or _goal(),)),
        workspace=workspace or CognitiveWorkspace(),
        memory=ActiveMemoryStore(),
        world_model=_model(),
        actions=(action or _action(),),
        calibration=calibration,
    )


def test_executive_returns_plan_ready_without_crossing_authority() -> None:
    """A bounded low-risk plan may enter governance but is not executed."""
    decision = _controller_decision()

    assert decision.status is ExecutiveDecisionStatus.PLAN_READY
    assert decision.plan is not None
    assert decision.may_enter_governance()


def test_executive_requires_human_for_authority_action() -> None:
    """Declared authority boundaries must survive planning."""
    decision = _controller_decision(action=_action(authority_required=True))

    assert decision.status is ExecutiveDecisionStatus.REQUIRES_HUMAN
    assert decision.blockers


def test_executive_blocks_plan_above_goal_risk_limit() -> None:
    """A found plan must still fail a declared risk limit."""
    workspace = CognitiveWorkspace().admit(
        WorkspaceItem.create(
            item_id="risk",
            kind=WorkspaceItemKind.RISK,
            content="The simulated action exceeds the declared risk budget.",
            confidence=1.0,
            salience=1.0,
            evidence_digests=(_digest("risk"),),
        )
    )
    decision = _controller_decision(
        goal=_goal(risk_limit=0.1),
        action=_action(risk=0.5),
        workspace=workspace,
    )

    assert decision.status is ExecutiveDecisionStatus.BLOCKED_RISK
    assert not decision.may_enter_governance()


def test_executive_blocks_miscalibrated_confidence() -> None:
    """Poor forecast calibration must be able to stop planning."""
    uncertainty = UncertaintyLedger.create(
        (
            CalibrationObservation.create(
                observation_id="overconfident",
                capability_id="planning",
                predicted_probability=1.0,
                observed=False,
                evidence_digest=_digest("calibration"),
                context="Failed held-out planning trial.",
            ),
        )
    )

    decision = _controller_decision(uncertainty=uncertainty)

    assert decision.status is ExecutiveDecisionStatus.BLOCKED_UNCERTAINTY
    assert decision.plan is None


def test_governance_bridge_preserves_action_identity_and_human_boundary() -> None:
    """Cognition must enter the existing proposal path rather than execute directly."""
    decision = _controller_decision(action=_action(authority_required=True))

    result = CognitiveProposalBridge().bridge(decision=decision, cycle=3)

    assert result.proposal.cycle == 3
    assert result.proposal.proposed_actions[0].action_id.value == "prepare-machine"
    assert result.proposal.proposed_actions[0].requires_human_boundary
    assert result.proposal.claims[0].status is ClaimStatus.PARTIAL
    assert result.receipt.executive_decision_digest == decision.digest()


def test_governance_bridge_rejects_blocked_decision() -> None:
    """A blocked cognitive decision must not be converted into a proposal packet."""
    decision = _controller_decision(goal=_goal(risk_limit=0.0), action=_action(risk=0.5))

    with pytest.raises(FoundationError, match="plan-ready"):
        CognitiveProposalBridge().bridge(decision=decision, cycle=0)


def _measure(capability: str, score: float) -> CapabilityMeasure:
    return CapabilityMeasure.create(
        capability_id=capability,
        score=score,
        evidence_digests=(_digest(f"{capability}-{score}"),),
        limitation="Measured only by the declared deterministic evaluation.",
    )


def test_adaptation_targets_weakest_measured_capability() -> None:
    """Adaptation proposals must be evidence-driven and remain unapproved."""
    model = SelfModel((_measure("memory", 0.8), _measure("planning", 0.4)))

    proposal = AdaptationController().propose_for_weakest(
        self_model=model,
        description="Evaluate an alternate bounded planning heuristic.",
        expected_benefit=0.2,
        regression_risk=0.1,
        supporting_evidence=(model.digest(),),
    )

    assert proposal.target_capability.value == "planning"
    assert proposal.status is ImprovementStatus.PROPOSED
    assert not proposal.may_enter_validation()


def test_regression_report_rejects_hidden_capability_loss() -> None:
    """A target improvement must not hide a regression elsewhere."""
    before = SelfModel((_measure("memory", 0.8), _measure("planning", 0.4)))
    after = SelfModel((_measure("memory", 0.5), _measure("planning", 0.7)))
    controller = AdaptationController(permitted_regression=0.05)
    proposal = controller.propose_for_weakest(
        self_model=before,
        description="Evaluate a planning strategy change.",
        expected_benefit=0.3,
        regression_risk=0.2,
        supporting_evidence=(before.digest(),),
    )

    report = controller.compare(proposal=proposal, before=before, after=after)

    assert report.has_regression()
    assert not report.may_request_validation()
    assert any(
        item.capability_id.value == "memory" and item.outcome is RegressionOutcome.REGRESSED
        for item in report.findings
    )


def test_regression_report_requires_complete_measurement() -> None:
    """Missing post-change measures must remain an incomplete result."""
    before = SelfModel((_measure("memory", 0.8), _measure("planning", 0.4)))
    after = SelfModel((_measure("planning", 0.7),))
    controller = AdaptationController()
    proposal = controller.propose_for_weakest(
        self_model=before,
        description="Evaluate a planning strategy change.",
        expected_benefit=0.3,
        regression_risk=0.2,
        supporting_evidence=(before.digest(),),
    )

    report = controller.compare(proposal=proposal, before=before, after=after)

    assert not report.complete()
    assert not report.may_request_validation()
