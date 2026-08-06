"""Human-review docket assembly for IX-Sally blocker visibility."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.actions import ActionStatus, BoundedActionRecord
from ix_sally.cycles import NinefoldCyclePacket
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.evidence_support import EvidenceSupportFinding
from ix_sally.forge_results import ForgeResultRecord, ForgeResultStatus
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.stage_gate import RunStageGate
from ix_sally.stage_readiness import RunStage, RunStageSnapshot
from ix_sally.state import NinefoldRunState


class HumanReviewDocketTargetType(StrEnum):
    """Human-review docket target kinds."""

    BOUNDED_ACTION = "bounded_action"
    EVIDENCE_SUPPORT_FINDING = "evidence_support_finding"
    FORGE_RESULT = "forge_result"
    NINEFOLD_CYCLE = "ninefold_cycle"


class HumanReviewDocketSeverity(StrEnum):
    """Severity assigned to a human-review docket target."""

    REVIEW_REQUIRED = "review_required"
    BLOCKER = "blocker"
    TERMINATION = "termination"


@dataclass(frozen=True, slots=True)
class HumanReviewDocketTarget:
    """One target that explains why human review is active."""

    target_type: HumanReviewDocketTargetType
    target_id: CanonicalKey
    cycle: int
    target_digest: DigestRecord
    source_status: str
    severity: HumanReviewDocketSeverity
    summary: str
    rationale: str

    @classmethod
    def create(
        cls,
        *,
        target_type: HumanReviewDocketTargetType,
        target_id: str,
        cycle: int,
        target_digest: DigestRecord,
        source_status: str,
        severity: HumanReviewDocketSeverity,
        summary: str,
        rationale: str,
    ) -> HumanReviewDocketTarget:
        """Create a normalized human-review docket target."""
        if cycle < 0:
            raise FoundationError("human-review docket target cycle must not be negative")

        target_digest.require_algorithm("sha256")

        return cls(
            target_type=target_type,
            target_id=CanonicalKey.from_text(target_id, field_name="target_id"),
            cycle=cycle,
            target_digest=target_digest,
            source_status=require_text(source_status, field_name="source_status"),
            severity=severity,
            summary=require_text(summary, field_name="summary"),
            rationale=require_text(rationale, field_name="rationale"),
        )

    @classmethod
    def from_action(cls, action: BoundedActionRecord) -> HumanReviewDocketTarget:
        """Create a docket target from a review-bound or blocking bounded action."""
        if action.status is ActionStatus.HUMAN_REVIEW_REQUIRED:
            severity = HumanReviewDocketSeverity.REVIEW_REQUIRED
            rationale = action.boundary_note or "Bounded action requires human review."
        elif action.status in {ActionStatus.DENIED, ActionStatus.BLOCKED}:
            severity = HumanReviewDocketSeverity.BLOCKER
            rationale = action.boundary_note or "Bounded action blocks autonomous continuation."
        else:
            raise FoundationError("bounded action is not a human-review docket target")

        return cls.create(
            target_type=HumanReviewDocketTargetType.BOUNDED_ACTION,
            target_id=action.action_id.value,
            cycle=action.cycle,
            target_digest=action.digest(),
            source_status=action.status.value,
            severity=severity,
            summary=action.description,
            rationale=rationale,
        )

    @classmethod
    def from_evidence_support(
        cls,
        finding: EvidenceSupportFinding,
    ) -> HumanReviewDocketTarget:
        """Create a docket target from an evidence-support finding requiring review."""
        if not finding.requires_human_review():
            raise FoundationError("evidence support finding does not require human review")

        return cls.create(
            target_type=HumanReviewDocketTargetType.EVIDENCE_SUPPORT_FINDING,
            target_id=finding.finding_id.value,
            cycle=finding.cycle,
            target_digest=finding.digest(),
            source_status=finding.status.value,
            severity=HumanReviewDocketSeverity.REVIEW_REQUIRED,
            summary="IX-Verity evidence support finding requires human review.",
            rationale=finding.contradiction_note or finding.rationale,
        )

    @classmethod
    def from_forge_result(cls, result: ForgeResultRecord) -> HumanReviewDocketTarget:
        """Create a docket target from a Forge result requiring review."""
        if not result.requires_human_review():
            raise FoundationError("Forge result does not require human review")

        severity = (
            HumanReviewDocketSeverity.BLOCKER
            if result.status is ForgeResultStatus.BLOCKED
            else HumanReviewDocketSeverity.REVIEW_REQUIRED
        )
        rationale = (
            result.boundary_note or result.failure_reason or "Forge result requires human review."
        )

        return cls.create(
            target_type=HumanReviewDocketTargetType.FORGE_RESULT,
            target_id=result.result_id.value,
            cycle=result.cycle,
            target_digest=result.digest(),
            source_status=result.status.value,
            severity=severity,
            summary=result.summary,
            rationale=rationale,
        )

    @classmethod
    def from_cycle(cls, cycle: NinefoldCyclePacket) -> HumanReviewDocketTarget:
        """Create a docket target from a cycle packet requiring human review."""
        if not cycle.requires_human_review():
            raise FoundationError("ninefold cycle does not require human review")

        terminated_roles = cycle.terminated_by_roles()
        blocking_roles = cycle.blocking_roles()
        severity = (
            HumanReviewDocketSeverity.TERMINATION
            if terminated_roles
            else HumanReviewDocketSeverity.BLOCKER
        )
        role_names = terminated_roles or blocking_roles
        joined_roles = ", ".join(role.value for role in role_names)

        return cls.create(
            target_type=HumanReviewDocketTargetType.NINEFOLD_CYCLE,
            target_id=cycle.cycle_id.value,
            cycle=cycle.cycle,
            target_digest=cycle.digest(),
            source_status=cycle.status.value,
            severity=severity,
            summary=cycle.cycle_goal,
            rationale=f"Cycle artifact review required for role(s): {joined_roles}.",
        )

    def requires_decision(self) -> bool:
        """Return whether the target waits on a human decision."""
        return self.severity is HumanReviewDocketSeverity.REVIEW_REQUIRED

    def blocks_progress(self) -> bool:
        """Return whether the target blocks autonomous continuation."""
        return self.severity in {
            HumanReviewDocketSeverity.BLOCKER,
            HumanReviewDocketSeverity.TERMINATION,
        }

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible docket target."""
        return {
            "target_type": self.target_type.value,
            "target_id": self.target_id.value,
            "cycle": self.cycle,
            "target_digest": {
                "algorithm": self.target_digest.algorithm,
                "value": self.target_digest.value,
            },
            "source_status": self.source_status,
            "severity": self.severity.value,
            "summary": self.summary,
            "rationale": self.rationale,
            "requires_decision": self.requires_decision(),
            "blocks_progress": self.blocks_progress(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this docket target."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewDocket:
    """Receipt-grade docket explaining every active human-review target."""

    state_digest: DigestRecord
    snapshot_digest: DigestRecord
    gate_decision_digest: DigestRecord
    targets: tuple[HumanReviewDocketTarget, ...]

    @classmethod
    def create(
        cls,
        *,
        state_digest: DigestRecord,
        snapshot_digest: DigestRecord,
        gate_decision_digest: DigestRecord,
        targets: Iterable[HumanReviewDocketTarget],
    ) -> HumanReviewDocket:
        """Create a normalized human-review docket."""
        state_digest.require_algorithm("sha256")
        snapshot_digest.require_algorithm("sha256")
        gate_decision_digest.require_algorithm("sha256")

        normalized = tuple(targets)
        seen: set[tuple[str, str]] = set()
        for target in normalized:
            key = (target.target_type.value, target.target_id.value)
            if key in seen:
                raise FoundationError(
                    f"duplicate human-review docket target: {target.target_type.value}/"
                    f"{target.target_id.value}"
                )
            seen.add(key)

        if not normalized:
            raise FoundationError("human-review docket requires at least one target")

        return cls(
            state_digest=state_digest,
            snapshot_digest=snapshot_digest,
            gate_decision_digest=gate_decision_digest,
            targets=normalized,
        )

    def targets_by_type(
        self,
        target_type: HumanReviewDocketTargetType,
    ) -> tuple[HumanReviewDocketTarget, ...]:
        """Return docket targets for the requested target type."""
        return tuple(target for target in self.targets if target.target_type is target_type)

    def review_required_targets(self) -> tuple[HumanReviewDocketTarget, ...]:
        """Return targets that require a human decision."""
        return tuple(target for target in self.targets if target.requires_decision())

    def blocking_targets(self) -> tuple[HumanReviewDocketTarget, ...]:
        """Return targets that block autonomous continuation."""
        return tuple(target for target in self.targets if target.blocks_progress())

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible human-review docket."""
        target_payload: JsonArray = []
        for target in self.targets:
            target_payload.append(target.to_payload())

        return {
            "state_digest": {
                "algorithm": self.state_digest.algorithm,
                "value": self.state_digest.value,
            },
            "snapshot_digest": {
                "algorithm": self.snapshot_digest.algorithm,
                "value": self.snapshot_digest.value,
            },
            "gate_decision_digest": {
                "algorithm": self.gate_decision_digest.algorithm,
                "value": self.gate_decision_digest.value,
            },
            "targets": target_payload,
            "target_count": len(self.targets),
            "review_required_count": len(self.review_required_targets()),
            "blocking_count": len(self.blocking_targets()),
            "bounded_action_count": len(
                self.targets_by_type(HumanReviewDocketTargetType.BOUNDED_ACTION)
            ),
            "evidence_support_finding_count": len(
                self.targets_by_type(HumanReviewDocketTargetType.EVIDENCE_SUPPORT_FINDING)
            ),
            "forge_result_count": len(
                self.targets_by_type(HumanReviewDocketTargetType.FORGE_RESULT)
            ),
            "ninefold_cycle_count": len(
                self.targets_by_type(HumanReviewDocketTargetType.NINEFOLD_CYCLE)
            ),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this human-review docket."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewDocketBuilder:
    """Builds human-review dockets only when human review is the active stage."""

    gate: RunStageGate

    @classmethod
    def create(cls) -> HumanReviewDocketBuilder:
        """Create a human-review docket builder."""
        return cls(gate=RunStageGate())

    def build(self, *, state: NinefoldRunState) -> HumanReviewDocket:
        """Build a docket for the currently active human-review stage."""
        snapshot = RunStageSnapshot.from_state(state)
        decision = self.gate.require(
            state=state,
            expected_stage=RunStage.HUMAN_REVIEW,
        )

        return HumanReviewDocket.create(
            state_digest=state.digest(),
            snapshot_digest=snapshot.digest(),
            gate_decision_digest=decision.digest(),
            targets=self._targets_from_state(state),
        )

    def _targets_from_state(
        self,
        state: NinefoldRunState,
    ) -> tuple[HumanReviewDocketTarget, ...]:
        """Collect all active human-review targets from state ledgers."""
        targets: list[HumanReviewDocketTarget] = []

        for action in state.actions.blocked_actions():
            targets.append(HumanReviewDocketTarget.from_action(action))

        for finding in state.evidence_support.human_review_findings():
            targets.append(HumanReviewDocketTarget.from_evidence_support(finding))

        for result in state.forge_results.human_review_results():
            targets.append(HumanReviewDocketTarget.from_forge_result(result))

        for cycle in state.cycles.human_review_cycles():
            targets.append(HumanReviewDocketTarget.from_cycle(cycle))

        return tuple(targets)
