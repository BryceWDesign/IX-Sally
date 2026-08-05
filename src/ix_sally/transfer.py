"""IX-Transfer trial packets for governed generalization testing."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifact, AgentArtifactKind
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_optional_text, require_text


class TransferStatus(StrEnum):
    """Status assigned to an IX-Transfer generalization trial."""

    PENDING = "pending"
    PASSED = "passed"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class TransferTrial:
    """A trial that tests whether a learned pattern transfers beyond its origin."""

    trial_id: CanonicalKey
    cycle: int
    source_digest: DigestRecord
    target_context: str
    invariant_under_test: str
    status: TransferStatus = TransferStatus.PENDING
    observed_result: str | None = None
    evidence_digest: DigestRecord | None = None
    failure_note: str | None = None
    boundary_note: str | None = None

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        source_digest: DigestRecord,
        target_context: str,
        invariant_under_test: str,
        status: TransferStatus = TransferStatus.PENDING,
        observed_result: str | None = None,
        evidence_digest: DigestRecord | None = None,
        failure_note: str | None = None,
        boundary_note: str | None = None,
        trial_id: CanonicalKey | None = None,
    ) -> TransferTrial:
        """Create a normalized IX-Transfer trial."""
        if cycle < 0:
            raise FoundationError("transfer trial cycle must not be negative")

        source_digest.require_algorithm("sha256")
        if evidence_digest is not None:
            evidence_digest.require_algorithm("sha256")

        normalized_context = require_text(target_context, field_name="target_context")
        normalized_invariant = require_text(
            invariant_under_test,
            field_name="invariant_under_test",
        )
        normalized_observed = require_optional_text(
            observed_result,
            field_name="observed_result",
        )
        normalized_failure = require_optional_text(failure_note, field_name="failure_note")
        normalized_boundary = require_optional_text(boundary_note, field_name="boundary_note")

        if status is not TransferStatus.PENDING and normalized_observed is None:
            raise FoundationError("resolved transfer trials require an observed result")

        if status is TransferStatus.PASSED and evidence_digest is None:
            raise FoundationError("passed transfer trials require an evidence digest")

        if status in {TransferStatus.PARTIAL, TransferStatus.FAILED}:
            if normalized_failure is None:
                raise FoundationError("partial or failed transfer trials require a failure note")

        if status is TransferStatus.BLOCKED and normalized_boundary is None:
            raise FoundationError("blocked transfer trials require a boundary note")

        return cls(
            trial_id=trial_id
            or CanonicalKey.from_text(
                f"ix-transfer-{cycle}-{normalized_context}-{normalized_invariant}",
                field_name="trial_id",
            ),
            cycle=cycle,
            source_digest=source_digest,
            target_context=normalized_context,
            invariant_under_test=normalized_invariant,
            status=status,
            observed_result=normalized_observed,
            evidence_digest=evidence_digest,
            failure_note=normalized_failure,
            boundary_note=normalized_boundary,
        )

    def passed(self) -> bool:
        """Return whether this transfer trial passed."""
        return self.status is TransferStatus.PASSED

    def needs_repair(self) -> bool:
        """Return whether the transfer result requires repair before learning."""
        return self.status in {TransferStatus.PARTIAL, TransferStatus.FAILED}

    def blocks_progress(self) -> bool:
        """Return whether the transfer result blocks autonomous progress."""
        return self.status is TransferStatus.BLOCKED

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible transfer trial representation."""
        return {
            "trial_id": self.trial_id.value,
            "cycle": self.cycle,
            "source_digest": {
                "algorithm": self.source_digest.algorithm,
                "value": self.source_digest.value,
            },
            "target_context": self.target_context,
            "invariant_under_test": self.invariant_under_test,
            "status": self.status.value,
            "observed_result": self.observed_result,
            "evidence_digest": (
                {
                    "algorithm": self.evidence_digest.algorithm,
                    "value": self.evidence_digest.value,
                }
                if self.evidence_digest is not None
                else None
            ),
            "failure_note": self.failure_note,
            "boundary_note": self.boundary_note,
            "passed": self.passed(),
            "needs_repair": self.needs_repair(),
            "blocks_progress": self.blocks_progress(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this transfer trial."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class TransferTrialPacket:
    """Structured IX-Transfer packet containing generalization trial results."""

    packet_id: CanonicalKey
    cycle: int
    transfer_summary: str
    trials: tuple[TransferTrial, ...]

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        transfer_summary: str,
        trials: Iterable[TransferTrial],
        packet_id: CanonicalKey | None = None,
    ) -> TransferTrialPacket:
        """Create a normalized IX-Transfer trial packet."""
        if cycle < 0:
            raise FoundationError("transfer packet cycle must not be negative")

        normalized_summary = require_text(transfer_summary, field_name="transfer_summary")
        normalized_trials = tuple(trials)

        if not normalized_trials:
            raise FoundationError("transfer packet requires at least one trial")

        for trial in normalized_trials:
            if trial.cycle != cycle:
                raise FoundationError("transfer trials must match packet cycle")

        return cls(
            packet_id=packet_id
            or CanonicalKey.from_text(
                f"ix-transfer-{cycle}-{normalized_summary}",
                field_name="packet_id",
            ),
            cycle=cycle,
            transfer_summary=normalized_summary,
            trials=normalized_trials,
        )

    def passed_count(self) -> int:
        """Return the number of passing transfer trials."""
        return sum(1 for trial in self.trials if trial.passed())

    def repair_count(self) -> int:
        """Return the number of transfer trials requiring repair."""
        return sum(1 for trial in self.trials if trial.needs_repair())

    def blocked_count(self) -> int:
        """Return the number of transfer trials blocked by boundary conditions."""
        return sum(1 for trial in self.trials if trial.blocks_progress())

    def has_blocker(self) -> bool:
        """Return whether this packet contains a blocking transfer trial."""
        return self.blocked_count() > 0

    def to_artifact(self) -> AgentArtifact:
        """Convert this packet into a shared runtime artifact."""
        return AgentArtifact.create(
            cycle=self.cycle,
            role=AgentRole.TRANSFER,
            kind=AgentArtifactKind.TRANSFER_RESULT,
            summary=f"IX-Transfer recorded {len(self.trials)} transfer trial(s).",
            referenced_digests=tuple(trial.digest() for trial in self.trials),
            data=self.to_payload(),
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible transfer packet representation."""
        trials_payload: JsonArray = []
        for trial in self.trials:
            trials_payload.append(trial.to_payload())

        return {
            "packet_id": self.packet_id.value,
            "cycle": self.cycle,
            "transfer_summary": self.transfer_summary,
            "trials": trials_payload,
            "passed_count": self.passed_count(),
            "repair_count": self.repair_count(),
            "blocked_count": self.blocked_count(),
            "has_blocker": self.has_blocker(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this transfer packet."""
        return DigestRecord.from_payload(self.to_payload())
