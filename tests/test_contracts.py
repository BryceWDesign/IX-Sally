

from __future__ import annotations

import pytest
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.foundation import FoundationError


def test_autonomy_contract_normalizes_core_fields() -> None:
    contract = AutonomyContract.create(
        goal="  Let governed agents inspect a small build request. ",
        mode=AutonomyMode.OBSERVE,
        max_cycles=3,
        non_goals=("  no production deployment  ",),
        allowed_tools=(" File Reader ", "Test Runner"),
        doctrine_keys=("Output is not evidence", "Memory is not truth"),
    )

    assert contract.goal == "Let governed agents inspect a small build request."
    assert contract.non_goals == ("no production deployment",)
    assert [tool.value for tool in contract.allowed_tools] == ["file-reader", "test-runner"]
    assert [key.value for key in contract.doctrine_keys] == [
        "output-is-not-evidence",
        "memory-is-not-truth",
    ]
    assert contract.memory_writes_allowed is False
    assert contract.network_allowed is False
    assert contract.human_boundary_required is True


def test_autonomy_contract_rejects_zero_cycles() -> None:
    with pytest.raises(FoundationError, match="max_cycles must be at least 1"):
        AutonomyContract.create(
            goal="Run chamber.",
            mode=AutonomyMode.RESEARCH,
            max_cycles=0,
        )


def test_autonomy_contract_requires_allowed_tool() -> None:
    contract = AutonomyContract.create(
        goal="Run chamber.",
        mode=AutonomyMode.TEST,
        max_cycles=1,
        allowed_tools=("test-runner",),
    )

    contract.require_tool_allowed("Test Runner")

    with pytest.raises(FoundationError, match="tool is not allowed"):
        contract.require_tool_allowed("network-client")


def test_autonomy_contract_requires_bound_doctrine_key() -> None:
    contract = AutonomyContract.create(
        goal="Run chamber.",
        mode=AutonomyMode.OBSERVE,
        max_cycles=1,
        doctrine_keys=("output-is-not-evidence",),
    )

    contract.require_doctrine_key("Output Is Not Evidence")

    with pytest.raises(FoundationError, match="doctrine key is not bound"):
        contract.require_doctrine_key("memory-is-not-truth")


def test_autonomy_contract_payload_is_stable() -> None:
    contract = AutonomyContract.create(
        goal="Run chamber.",
        mode=AutonomyMode.BUILD,
        max_cycles=2,
        non_goals=("no external network",),
        allowed_tools=("sandbox-executor",),
        doctrine_keys=("generated-intent-is-not-permission-to-act",),
        memory_writes_allowed=True,
    )

    assert contract.to_payload() == {
        "goal": "Run chamber.",
        "mode": "build",
        "max_cycles": 2,
        "non_goals": ["no external network"],
        "allowed_tools": ["sandbox-executor"],
        "doctrine_keys": ["generated-intent-is-not-permission-to-act"],
        "memory_writes_allowed": True,
        "network_allowed": False,
        "human_boundary_required": True,
    }


def test_contract_digest_changes_when_boundary_changes() -> None:
    first = AutonomyContract.create(
        goal="Run chamber.",
        mode=AutonomyMode.OBSERVE,
        max_cycles=1,
        network_allowed=False,
    )
    second = AutonomyContract.create(
        goal="Run chamber.",
        mode=AutonomyMode.OBSERVE,
        max_cycles=1,
        network_allowed=True,
    )

    assert first.digest().value != second.digest().value
