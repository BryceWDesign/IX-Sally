from __future__ import annotations

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.forge_results import ForgeResultRecord, ForgeResultStatus
from ix_sally.orchestration import StageAdvanceKind
from ix_sally.orchestration_loop import StageLoopRunner, StageLoopStopReason
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Run bounded orchestration loop.",
        mode=AutonomyMode.TEST,
        max_cycles=2,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _proposed_action() -> BoundedActionRecord:
    return BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.SALLY,
        description="Run tests.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload(
            {"proposal_action": "run tests"},
        ),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )


def test_stage_loop_runner_stops_for_proposal_input_on_fresh_state() -> None:
    state = _state()

    result = StageLoopRunner.create().run_until_stop(state=state, max_steps=5)

    assert result.stop_reason is StageLoopStopReason.EXTERNAL_INPUT_REQUIRED
    assert result.stopped_for_external_input() is True
    assert result.executed_steps() == 1
    assert result.latest_kind() is StageAdvanceKind.WAITING_FOR_PROPOSAL
    assert result.state == state


def test_stage_loop_runner_advances_to_forge_result_wait() -> None:
    state = _state().with_action(_proposed_action())

    result = StageLoopRunner.create().run_until_stop(state=state, max_steps=10)

    assert result.stop_reason is StageLoopStopReason.EXTERNAL_INPUT_REQUIRED
    assert result.executed_steps() == 4
    assert result.latest_kind() is StageAdvanceKind.WAITING_FOR_FORGE_RESULTS
    assert result.state.executable_action_count() == 1
    assert result.state.queued_execution_count() == 0
    assert result.state.dispatched_execution_count() == 1
    assert result.forge_results_consumed == 0


def test_stage_loop_runner_obeys_step_limit_before_external_wait() -> None:
    state = _state().with_action(_proposed_action())

    result = StageLoopRunner.create().run_until_stop(state=state, max_steps=1)

    assert result.stop_reason is StageLoopStopReason.STEP_LIMIT_REACHED
    assert result.stopped_for_step_limit() is True
    assert result.executed_steps() == 1
    assert result.latest_kind() is StageAdvanceKind.AUTHORITY_PROCESSED
    assert result.final_snapshot.stage is RunStage.EXECUTION_PLANNING


def test_stage_loop_runner_consumes_forge_results_only_at_forge_result_stage() -> None:
    runner = StageLoopRunner.create()
    waiting = runner.run_until_stop(
        state=_state().with_action(_proposed_action()),
        max_steps=10,
    )
    item = waiting.state.execution_queue.dispatched_items()[0]
    action = waiting.state.actions.require_action(item.action_id.value)
    forge_result = ForgeResultRecord.from_dispatched_item(
        item=item,
        action=action,
        status=ForgeResultStatus.PASSED,
        summary="Forge test execution passed.",
        observed_output="1 passed",
    )

    result = runner.run_until_stop(
        state=waiting.state,
        max_steps=10,
        forge_results=(forge_result,),
    )

    assert result.forge_results_consumed == 1
    assert result.state.executed_action_count() == 1
    assert result.state.passed_forge_result_count() == 1
    assert result.latest_kind() is StageAdvanceKind.WAITING_FOR_PROPOSAL
    assert result.stop_reason is StageLoopStopReason.EXTERNAL_INPUT_REQUIRED


def test_stage_loop_result_payload_and_digest_are_stable() -> None:
    state = _state()
    first = StageLoopRunner.create().run_until_stop(state=state, max_steps=5)
    second = StageLoopRunner.create().run_until_stop(state=state, max_steps=5)

    payload = first.to_payload()

    assert payload["stop_reason"] == StageLoopStopReason.EXTERNAL_INPUT_REQUIRED.value
    assert payload["executed_steps"] == 1
    assert payload["latest_kind"] == StageAdvanceKind.WAITING_FOR_PROPOSAL.value
    assert first.digest() == second.digest()
