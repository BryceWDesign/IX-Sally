"""Functional ninefold cognition without theatrical agent conversation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_sally.agents import AgentRole, default_agent_role_registry
from ix_sally.cognition.active_memory import ActiveMemoryStore
from ix_sally.cognition.learning import LearningLedger
from ix_sally.cognition.planning import ActionSpec, DeterministicPlanner, Plan
from ix_sally.cognition.workspace import CognitiveWorkspace, WorkspaceItemKind
from ix_sally.cognition.world_model import FactPattern, FactStatus, WorldModel
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


@dataclass(frozen=True, slots=True)
class RoleFinding:
    """One inspectable output from a ninefold cognitive function."""

    role: AgentRole
    summary: str
    detail: str
    blocking: bool = False
    evidence_digests: tuple[DigestRecord, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        role: AgentRole,
        summary: str,
        detail: str,
        blocking: bool = False,
        evidence_digests: Iterable[DigestRecord] = (),
    ) -> RoleFinding:
        """Create a normalized role finding."""
        evidence = tuple(evidence_digests)
        for digest in evidence:
            digest.require_algorithm("sha256")
        return cls(
            role=role,
            summary=require_text(summary, field_name="summary"),
            detail=require_text(detail, field_name="detail"),
            blocking=blocking,
            evidence_digests=evidence,
        )

    def to_payload(self) -> JsonObject:
        """Return a canonical role-finding payload."""
        evidence: JsonArray = [
            {"algorithm": digest.algorithm, "value": digest.value}
            for digest in self.evidence_digests
        ]
        return {
            "role": self.role.value,
            "summary": self.summary,
            "detail": self.detail,
            "blocking": self.blocking,
            "evidence_digests": evidence,
        }


@dataclass(frozen=True, slots=True)
class NinefoldCognitiveCycle:
    """One coordinated cycle across all nine non-overlapping cognitive functions."""

    cycle_id: CanonicalKey
    task: str
    findings: tuple[RoleFinding, ...]
    proposed_plan: Plan | None

    def __post_init__(self) -> None:
        """Require complete exactly-once coverage of the nine canonical roles."""
        roles = [finding.role for finding in self.findings]
        if len(roles) != len(AgentRole) or set(roles) != set(AgentRole):
            raise FoundationError("ninefold cycle requires exactly one finding per role")

    def blocking_findings(self) -> tuple[RoleFinding, ...]:
        """Return findings that block action or unsupported conclusions."""
        return tuple(finding for finding in self.findings if finding.blocking)

    def to_payload(self) -> JsonObject:
        """Return a canonical cycle payload."""
        findings: JsonArray = [finding.to_payload() for finding in self.findings]
        plan_payload: JsonObject | None = None
        if self.proposed_plan is not None:
            plan_payload = self.proposed_plan.to_payload()
        return {
            "cycle_id": self.cycle_id.value,
            "task": self.task,
            "findings": findings,
            "blocking_count": len(self.blocking_findings()),
            "proposed_plan": plan_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic cycle identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class NinefoldCoordinator:
    """Coordinate functional roles from shared state instead of simulated personalities."""

    planner: DeterministicPlanner = DeterministicPlanner()

    def run(
        self,
        *,
        task: str,
        workspace: CognitiveWorkspace,
        memory: ActiveMemoryStore,
        world_model: WorldModel,
        learning: LearningLedger,
        actions: Iterable[ActionSpec] = (),
        goal: FactPattern | None = None,
    ) -> NinefoldCognitiveCycle:
        """Run one deterministic, receipt-producing ninefold cognitive cycle."""
        normalized_task = require_text(task, field_name="task")
        action_catalog = tuple(actions)
        registry = default_agent_role_registry()
        registry.require_complete_ninefold()
        focus = workspace.focus()
        retrievals = memory.retrieve(normalized_task, limit=3)
        predictions = world_model.predict()
        plan = None
        if goal is not None:
            plan = self.planner.plan(
                world_model=world_model,
                actions=action_catalog,
                goal=goal,
            )

        risks = tuple(
            item for item in workspace.items
            if item.kind is WorkspaceItemKind.RISK
        )
        hypotheses = tuple(
            item for item in workspace.items
            if item.kind is WorkspaceItemKind.HYPOTHESIS
        )
        unsupported_hypotheses = tuple(
            item for item in hypotheses if not item.evidence_digests
        )
        observed_count = sum(
            1 for fact in world_model.facts if fact.status is FactStatus.OBSERVED
        )
        verified_memory_count = sum(
            1 for entry in memory.entries if entry.is_retrievable_truth()
        )
        authority_block = plan is not None and plan.requires_human_authority()
        findings = (
            RoleFinding.create(
                role=AgentRole.SALLY,
                summary="Constructed current task proposal context.",
                detail=(
                    f"Task has {len(focus)} focused workspace items and "
                    f"{len(action_catalog)} declared planning actions."
                ),
                evidence_digests=(workspace.digest(),),
            ),
            RoleFinding.create(
                role=AgentRole.BUTCH,
                summary="Tested assumptions for unsupported hypotheses.",
                detail=(
                    f"Found {len(unsupported_hypotheses)} hypotheses without "
                    "explicit evidence bindings."
                ),
                blocking=bool(unsupported_hypotheses),
                evidence_digests=(workspace.digest(),),
            ),
            RoleFinding.create(
                role=AgentRole.VERITY,
                summary="Measured evidence-backed state.",
                detail=(
                    f"World model contains {observed_count} observed facts and memory "
                    f"contains {verified_memory_count} verified entries."
                ),
                evidence_digests=(world_model.digest(), memory.digest()),
            ),
            RoleFinding.create(
                role=AgentRole.ORACLE,
                summary="Produced causal predictions before action.",
                detail=f"Generated {len(predictions)} evidence-bound predictions.",
                evidence_digests=(world_model.digest(),),
            ),
            RoleFinding.create(
                role=AgentRole.FORGE,
                summary="Evaluated the bounded execution path.",
                detail=(
                    "No goal was supplied for planning."
                    if plan is None
                    else f"Planner result: {plan.status.value}."
                ),
                blocking=(
                    plan is not None
                    and not plan.actions
                    and plan.status is PlanStatus.NOT_FOUND
                ),
                evidence_digests=(plan.digest(),) if plan is not None else (),
            ),
            RoleFinding.create(
                role=AgentRole.MNEMOSYNE,
                summary="Retrieved relevant memory without promoting candidates to truth.",
                detail=f"Retrieved {len(retrievals)} scored memory entries.",
                evidence_digests=(memory.digest(),),
            ),
            RoleFinding.create(
                role=AgentRole.SENTINEL,
                summary="Checked risk and human authority boundaries.",
                detail=(
                    f"Workspace has {len(risks)} explicit risks; "
                    f"human authority required: {authority_block}."
                ),
                blocking=authority_block,
                evidence_digests=(workspace.digest(),) + ((plan.digest(),) if plan else ()),
            ),
            RoleFinding.create(
                role=AgentRole.TRANSFER,
                summary="Measured available learning and retention evidence.",
                detail=(
                    f"Learning ledger contains {len(learning.profiles)} skill profiles "
                    f"from {len(learning.outcomes)} outcomes."
                ),
                evidence_digests=(learning.digest(),),
            ),
            RoleFinding.create(
                role=AgentRole.CLERK,
                summary="Recorded the complete deterministic cycle state.",
                detail="All role findings are digest-bound and ordered by canonical role.",
                evidence_digests=(
                    workspace.digest(),
                    memory.digest(),
                    world_model.digest(),
                    learning.digest(),
                ),
            ),
        )
        ordered = tuple(
            next(finding for finding in findings if finding.role is role)
            for role in AgentRole
        )
        cycle_seed = DigestRecord.from_payload(
            {
                "task": normalized_task,
                "workspace": workspace.digest().value,
                "memory": memory.digest().value,
                "world": world_model.digest().value,
                "learning": learning.digest().value,
            }
        )
        return NinefoldCognitiveCycle(
            cycle_id=CanonicalKey.from_text(
                f"cognitive-cycle-{cycle_seed.value[:20]}",
                field_name="cycle_id",
            ),
            task=normalized_task,
            findings=ordered,
            proposed_plan=plan,
        )
