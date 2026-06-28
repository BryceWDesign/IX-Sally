from __future__ import annotations

import pytest

from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifact, AgentArtifactKind
from ix_sally.cycles import CycleCoordinationStatus, NinefoldCycleLedger, NinefoldCyclePacket
from ix_sally.foundation import CanonicalKey, FoundationError


def _artifact(
    *,
    role: AgentRole,
    kind: AgentArtifactKind,
    cycle: int = 1,
    data: dict[str, object] | None = None,
) -> AgentArtifact:
    return AgentArtifact.create(
        cycle=cycle,
        role=role,
        kind=kind,
        summary=f"{role.value} artifact.",
        data=data or {},
    )


def _complete_artifacts(*, cycle: int = 1) -> tuple[AgentArtifact, ...]:
    return (
        _artifact(role=AgentRole.SALLY, kind=AgentArtifactKind.PROPOSAL, cycle=cycle),
        _artifact(role=AgentRole.BUTCH, kind=AgentArtifactKind.FALSIFICATION, cycle=cycle),
        _artifact(role=AgentRole.VERITY, kind=AgentArtifactKind.EVIDENCE_JUDGMENT, cycle=cycle),
        _artifact(role=AgentRole.ORACLE, kind=AgentArtifactKind.PREDICTION, cycle=cycle),
        _artifact(role=AgentRole.FORGE, kind=AgentArtifactKind.EXECUTION_RECEIPT, cycle=cycle),
        _artifact(role=AgentRole.MNEMOSYNE, kind=AgentArtifactKind.MEMORY_DECISION, cycle=cycle),
        _artifact(role=AgentRole.SENTINEL, kind=AgentArtifactKind.BOUNDARY_REPORT, cycle=cycle),
        _artifact(role=AgentRole.TRANSFER, kind=AgentArtifactKind.TRANSFER_RESULT, cycle=cycle),
        _artifact(role=AgentRole.CLERK, kind=AgentArtifactKind.DOSSIER_ENTRY, cycle=cycle),
    )


def test_ninefold_cycle_packet_requires_non_negative_cycle() -> None:
    with pytest.raises(FoundationError, match="ninefold cycle must not be negative"):
        NinefoldCyclePacket.create(
            cycle=-1,
            cycle_goal="Invalid cycle.",
            artifacts=_complete_artifacts(cycle=1),
        )


def test_ninefold_cycle_packet_requires_artifacts() -> None:
    with pytest.raises(FoundationError, match="ninefold cycle requires artifacts"):
        NinefoldCyclePacket.create(
            cycle=1,
            cycle_goal="No artifacts.",
            artifacts=(),
        )


def test_ninefold_cycle_packet_rejects_artifact_cycle_mismatch() -> None:
    artifacts = _complete_artifacts(cycle=1)
    mismatched = (
        *artifacts[:-1],
        _artifact(role=AgentRole.CLERK, kind=AgentArtifactKind.DOSSIER_ENTRY, cycle=2),
    )

    with pytest.raises(FoundationError, match="artifacts must match packet cycle"):
        NinefoldCyclePacket.create(
            cycle=1,
            cycle_goal="Mismatch.",
            artifacts=mismatched,
        )


def test_ninefold_cycle_packet_rejects_duplicate_role_artifact() -> None:
    artifacts = (
        _artifact(role=AgentRole.SALLY, kind=AgentArtifactKind.PROPOSAL),
        _artifact(role=AgentRole.SALLY, kind=AgentArtifactKind.PROPOSAL),
    )

    with pytest.raises(FoundationError, match="duplicate ninefold role artifact"):
        NinefoldCyclePacket.create(
            cycle=1,
            cycle_goal="Duplicate role.",
            artifacts=artifacts,
        )


def test_ninefold_cycle_packet_requires_all_nine_roles() -> None:
    artifacts = _complete_artifacts()[:-1]

    with pytest.raises(FoundationError, match="missing ninefold cycle role artifacts"):
        NinefoldCyclePacket.create(
            cycle=1,
            cycle_goal="Incomplete cycle.",
            artifacts=artifacts,
        )


def test_ninefold_cycle_packet_normalizes_goal_and_generates_id() -> None:
    packet = NinefoldCyclePacket.create(
        cycle=1,
        cycle_goal="  Complete a bounded ninefold review. ",
        artifacts=_complete_artifacts(),
    )

    assert packet.cycle_id.value == "ninefold-cycle-1-complete-a-bounded-ninefold-review"
    assert packet.cycle_goal == "Complete a bounded ninefold review."
    assert packet.status is CycleCoordinationStatus.COMPLETE
    assert len(packet.artifacts) == 9


def test_ninefold_cycle_packet_returns_artifact_for_role() -> None:
    packet = NinefoldCyclePacket.create(
        cycle=1,
        cycle_goal="Complete a bounded ninefold review.",
        artifacts=_complete_artifacts(),
    )

    assert packet.artifact_for_role(AgentRole.SALLY).role is AgentRole.SALLY
    assert packet.artifact_for_role(AgentRole.CLERK).role is AgentRole.CLERK


def test_ninefold_cycle_packet_reports_blockers_and_human_review() -> None:
    artifacts = (
        _artifact(role=AgentRole.SALLY, kind=AgentArtifactKind.PROPOSAL),
        _artifact(role=AgentRole.BUTCH, kind=AgentArtifactKind.FALSIFICATION),
        _artifact(role=AgentRole.VERITY, kind=AgentArtifactKind.EVIDENCE_JUDGMENT),
        _artifact(role=AgentRole.ORACLE, kind=AgentArtifactKind.PREDICTION),
        _artifact(role=AgentRole.FORGE, kind=AgentArtifactKind.EXECUTION_RECEIPT),
        _artifact(role=AgentRole.MNEMOSYNE, kind=AgentArtifactKind.MEMORY_DECISION),
        _artifact(
            role=AgentRole.SENTINEL,
            kind=AgentArtifactKind.BOUNDARY_REPORT,
            data={"has_blocker": True, "terminates_run": True},
        ),
        _artifact(role=AgentRole.TRANSFER, kind=AgentArtifactKind.TRANSFER_RESULT),
        _artifact(
            role=AgentRole.CLERK,
            kind=AgentArtifactKind.DOSSIER_ENTRY,
            data={"requires_human_review": True},
        ),
    )
    packet = NinefoldCyclePacket.create(
        cycle=1,
        cycle_goal="Review blocked cycle.",
        artifacts=artifacts,
        status=CycleCoordinationStatus.TERMINATED,
    )

    assert packet.blocking_roles() == (AgentRole.SENTINEL,)
    assert packet.terminated_by_roles() == (AgentRole.SENTINEL,)
    assert packet.requires_human_review() is True


def test_ninefold_cycle_packet_payload_is_stable() -> None:
    packet = NinefoldCyclePacket.create(
        cycle_id=CanonicalKey.from_text("cycle-one", field_name="cycle_id"),
        cycle=1,
        cycle_goal="Complete a bounded ninefold review.",
        artifacts=_complete_artifacts(),
    )

    payload = packet.to_payload()

    assert payload["cycle_id"] == "cycle-one"
    assert payload["cycle"] == 1
    assert payload["cycle_goal"] == "Complete a bounded ninefold review."
    assert payload["status"] == "complete"
    assert payload["artifact_count"] == 9
    assert payload["blocking_roles"] == []
    assert payload["terminated_by_roles"] == []
    assert payload["requires_human_review"] is False


def test_ninefold_cycle_ledger_rejects_duplicate_cycle_ids() -> None:
    cycle_id = CanonicalKey.from_text("same-cycle", field_name="cycle_id")
    first = NinefoldCyclePacket.create(
        cycle_id=cycle_id,
        cycle=1,
        cycle_goal="First cycle.",
        artifacts=_complete_artifacts(cycle=1),
    )
    second = NinefoldCyclePacket.create(
        cycle_id=cycle_id,
        cycle=2,
        cycle_goal="Second cycle.",
        artifacts=_complete_artifacts(cycle=2),
    )

    with pytest.raises(FoundationError, match="duplicate ninefold cycle id"):
        NinefoldCycleLedger.create((first, second))


def test_ninefold_cycle_ledger_rejects_backward_cycles() -> None:
    first = NinefoldCyclePacket.create(
        cycle=2,
        cycle_goal="Second cycle.",
        artifacts=_complete_artifacts(cycle=2),
    )
    second = NinefoldCyclePacket.create(
        cycle=1,
        cycle_goal="First cycle.",
        artifacts=_complete_artifacts(cycle=1),
    )

    with pytest.raises(FoundationError, match="ledger must not move backward"):
        NinefoldCycleLedger.create((first, second))


def test_ninefold_cycle_ledger_appends_and_requires_cycle() -> None:
    packet = NinefoldCyclePacket.create(
        cycle=1,
        cycle_goal="Complete a bounded ninefold review.",
        artifacts=_complete_artifacts(),
    )
    ledger = NinefoldCycleLedger.create(()).append(packet)

    assert ledger.require_cycle(packet.cycle_id.value) == packet

    with pytest.raises(FoundationError, match="unknown ninefold cycle id"):
        ledger.require_cycle("missing-cycle")


def test_ninefold_cycle_ledger_filters_blocked_and_human_review_cycles() -> None:
    normal = NinefoldCyclePacket.create(
        cycle=1,
        cycle_goal="Normal cycle.",
        artifacts=_complete_artifacts(cycle=1),
    )
    blocked_artifacts = (
        _artifact(role=AgentRole.SALLY, kind=AgentArtifactKind.PROPOSAL, cycle=2),
        _artifact(role=AgentRole.BUTCH, kind=AgentArtifactKind.FALSIFICATION, cycle=2),
        _artifact(role=AgentRole.VERITY, kind=AgentArtifactKind.EVIDENCE_JUDGMENT, cycle=2),
        _artifact(role=AgentRole.ORACLE, kind=AgentArtifactKind.PREDICTION, cycle=2),
        _artifact(role=AgentRole.FORGE, kind=AgentArtifactKind.EXECUTION_RECEIPT, cycle=2),
        _artifact(
            role=AgentRole.MNEMOSYNE,
            kind=AgentArtifactKind.MEMORY_DECISION,
            cycle=2,
        ),
        _artifact(
            role=AgentRole.SENTINEL,
            kind=AgentArtifactKind.BOUNDARY_REPORT,
            cycle=2,
            data={"has_blocker": True},
        ),
        _artifact(role=AgentRole.TRANSFER, kind=AgentArtifactKind.TRANSFER_RESULT, cycle=2),
        _artifact(role=AgentRole.CLERK, kind=AgentArtifactKind.DOSSIER_ENTRY, cycle=2),
    )
    blocked = NinefoldCyclePacket.create(
        cycle=2,
        cycle_goal="Blocked cycle.",
        artifacts=blocked_artifacts,
        status=CycleCoordinationStatus.BLOCKED,
    )
    ledger = NinefoldCycleLedger.create((normal, blocked))

    assert ledger.blocked_cycles() == (blocked,)
    assert ledger.human_review_cycles() == (blocked,)


def test_ninefold_cycle_digest_changes_when_artifact_changes() -> None:
    first = NinefoldCyclePacket.create(
        cycle=1,
        cycle_goal="Review cycle.",
        artifacts=_complete_artifacts(),
    )
    changed_artifacts = (
        *_complete_artifacts()[:-1],
        _artifact(
            role=AgentRole.CLERK,
            kind=AgentArtifactKind.DOSSIER_ENTRY,
            data={"requires_human_review": True},
        ),
    )
    second = NinefoldCyclePacket.create(
        cycle=1,
        cycle_goal="Review cycle.",
        artifacts=changed_artifacts,
    )

    assert first.digest().value != second.digest().value
