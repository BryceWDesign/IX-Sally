from __future__ import annotations

import pytest

from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifactKind
from ix_sally.digest import DigestRecord
from ix_sally.executions import ExecutionStatus, ForgeExecutionPacket, ForgeExecutionReceipt
from ix_sally.foundation import CanonicalKey, FoundationError


def test_forge_execution_receipt_normalizes_fields_and_generates_id() -> None:
    receipt = ForgeExecutionReceipt.create(
        cycle=1,
        tool_key=" Test Runner ",
        command=(" python ", " -m ", " pytest "),
        sandboxed=True,
        status=ExecutionStatus.PASSED,
        summary="  Tests passed inside sandbox. ",
        exit_code=0,
    )

    assert receipt.receipt_id.value == "ix-forge-1-test-runner-tests-passed-inside-sandbox"
    assert receipt.tool_key.value == "test-runner"
    assert receipt.command == ("python", "-m", "pytest")
    assert receipt.summary == "Tests passed inside sandbox."
    assert receipt.succeeded() is True
    assert receipt.blocks_progress() is False


def test_forge_execution_receipt_rejects_negative_cycle() -> None:
    with pytest.raises(FoundationError, match="execution cycle must not be negative"):
        ForgeExecutionReceipt.create(
            cycle=-1,
            tool_key="test-runner",
            command=("pytest",),
            sandboxed=True,
            status=ExecutionStatus.PASSED,
            summary="Invalid cycle.",
            exit_code=0,
        )


def test_forge_execution_receipt_requires_command_part() -> None:
    with pytest.raises(FoundationError, match="execution command requires at least one part"):
        ForgeExecutionReceipt.create(
            cycle=1,
            tool_key="test-runner",
            command=(),
            sandboxed=True,
            status=ExecutionStatus.PASSED,
            summary="No command.",
            exit_code=0,
        )


def test_forge_execution_receipt_blocks_non_sandboxed_execution() -> None:
    with pytest.raises(FoundationError, match="non-sandboxed execution must be blocked"):
        ForgeExecutionReceipt.create(
            cycle=1,
            tool_key="test-runner",
            command=("pytest",),
            sandboxed=False,
            status=ExecutionStatus.PASSED,
            summary="Unsafe execution.",
            exit_code=0,
        )


def test_passed_receipt_requires_zero_exit_code() -> None:
    with pytest.raises(FoundationError, match="passed execution receipts require exit_code 0"):
        ForgeExecutionReceipt.create(
            cycle=1,
            tool_key="test-runner",
            command=("pytest",),
            sandboxed=True,
            status=ExecutionStatus.PASSED,
            summary="Invalid passed receipt.",
            exit_code=1,
        )


def test_failed_receipt_requires_nonzero_exit_code() -> None:
    with pytest.raises(FoundationError, match="failed execution receipts require"):
        ForgeExecutionReceipt.create(
            cycle=1,
            tool_key="test-runner",
            command=("pytest",),
            sandboxed=True,
            status=ExecutionStatus.FAILED,
            summary="Invalid failed receipt.",
            exit_code=0,
        )


def test_blocked_or_timed_out_receipt_requires_boundary_note() -> None:
    with pytest.raises(FoundationError, match="blocked or timed-out executions require"):
        ForgeExecutionReceipt.create(
            cycle=1,
            tool_key="network-client",
            command=("curl", "example.com"),
            sandboxed=True,
            status=ExecutionStatus.BLOCKED,
            summary="Network blocked.",
        )


def test_forge_execution_receipt_rejects_non_sha256_output_digest() -> None:
    digest = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        ForgeExecutionReceipt.create(
            cycle=1,
            tool_key="test-runner",
            command=("pytest",),
            sandboxed=True,
            status=ExecutionStatus.PASSED,
            summary="Invalid digest.",
            exit_code=0,
            stdout_digest=digest,
        )


def test_forge_execution_receipt_payload_is_stable() -> None:
    stdout_digest = DigestRecord.from_payload({"stdout": "passed"})
    stderr_digest = DigestRecord.from_payload({"stderr": ""})
    receipt = ForgeExecutionReceipt.create(
        receipt_id=CanonicalKey.from_text("receipt-one", field_name="receipt_id"),
        cycle=1,
        tool_key="test-runner",
        command=("python", "-m", "pytest"),
        sandboxed=True,
        status=ExecutionStatus.PASSED,
        summary="Tests passed.",
        exit_code=0,
        stdout_digest=stdout_digest,
        stderr_digest=stderr_digest,
    )

    assert receipt.to_payload() == {
        "receipt_id": "receipt-one",
        "cycle": 1,
        "tool_key": "test-runner",
        "command": ["python", "-m", "pytest"],
        "sandboxed": True,
        "status": "passed",
        "summary": "Tests passed.",
        "exit_code": 0,
        "stdout_digest": {
            "algorithm": "sha256",
            "value": stdout_digest.value,
        },
        "stderr_digest": {
            "algorithm": "sha256",
            "value": stderr_digest.value,
        },
        "boundary_note": None,
        "succeeded": True,
        "blocks_progress": False,
    }


def test_forge_execution_packet_requires_receipt() -> None:
    with pytest.raises(FoundationError, match="requires at least one receipt"):
        ForgeExecutionPacket.create(
            cycle=1,
            execution_summary="No receipts.",
            receipts=(),
        )


def test_forge_execution_packet_rejects_cycle_mismatch() -> None:
    receipt = ForgeExecutionReceipt.create(
        cycle=2,
        tool_key="test-runner",
        command=("pytest",),
        sandboxed=True,
        status=ExecutionStatus.PASSED,
        summary="Wrong cycle.",
        exit_code=0,
    )

    with pytest.raises(FoundationError, match="execution receipts must match packet cycle"):
        ForgeExecutionPacket.create(
            cycle=1,
            execution_summary="Review execution.",
            receipts=(receipt,),
        )


def test_forge_execution_packet_counts_receipt_statuses() -> None:
    passed = ForgeExecutionReceipt.create(
        cycle=1,
        tool_key="test-runner",
        command=("pytest",),
        sandboxed=True,
        status=ExecutionStatus.PASSED,
        summary="Tests passed.",
        exit_code=0,
    )
    failed = ForgeExecutionReceipt.create(
        cycle=1,
        tool_key="lint-runner",
        command=("ruff", "check", "."),
        sandboxed=True,
        status=ExecutionStatus.FAILED,
        summary="Lint failed.",
        exit_code=1,
    )
    blocked = ForgeExecutionReceipt.create(
        cycle=1,
        tool_key="network-client",
        command=("curl", "example.com"),
        sandboxed=True,
        status=ExecutionStatus.BLOCKED,
        summary="Network request blocked.",
        boundary_note="Network access is outside the autonomy contract.",
    )
    packet = ForgeExecutionPacket.create(
        cycle=1,
        execution_summary="Run bounded checks.",
        receipts=(passed, failed, blocked),
    )

    assert packet.passed_count() == 1
    assert packet.failed_count() == 1
    assert packet.blocked_count() == 1
    assert packet.has_blocker() is True


def test_forge_execution_packet_converts_to_artifact() -> None:
    receipt = ForgeExecutionReceipt.create(
        cycle=1,
        tool_key="test-runner",
        command=("pytest",),
        sandboxed=True,
        status=ExecutionStatus.PASSED,
        summary="Tests passed.",
        exit_code=0,
    )
    packet = ForgeExecutionPacket.create(
        cycle=1,
        execution_summary="Run tests.",
        receipts=(receipt,),
    )

    artifact = packet.to_artifact()

    assert artifact.role is AgentRole.FORGE
    assert artifact.kind is AgentArtifactKind.EXECUTION_RECEIPT
    assert artifact.summary == "IX-Forge recorded 1 execution receipt(s)."
    assert artifact.referenced_digests == (receipt.digest(),)
    assert artifact.data == packet.to_payload()


def test_forge_execution_packet_digest_changes_when_receipt_status_changes() -> None:
    first_receipt = ForgeExecutionReceipt.create(
        cycle=1,
        tool_key="test-runner",
        command=("pytest",),
        sandboxed=True,
        status=ExecutionStatus.PASSED,
        summary="Tests passed.",
        exit_code=0,
    )
    second_receipt = ForgeExecutionReceipt.create(
        cycle=1,
        tool_key="test-runner",
        command=("pytest",),
        sandboxed=True,
        status=ExecutionStatus.FAILED,
        summary="Tests failed.",
        exit_code=1,
    )
    first = ForgeExecutionPacket.create(
        cycle=1,
        execution_summary="Run tests.",
        receipts=(first_receipt,),
    )
    second = ForgeExecutionPacket.create(
        cycle=1,
        execution_summary="Run tests.",
        receipts=(second_receipt,),
    )

    assert first.digest().value != second.digest().value
