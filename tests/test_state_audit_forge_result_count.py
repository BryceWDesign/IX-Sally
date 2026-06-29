from __future__ import annotations

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.execution_queue import ExecutionQueueItem
from ix_sally.forge_results import ForgeResultRecord, ForgeResultStatus
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState
from ix_sally.state_audit import StateAuditor


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Audit dispatched Forge result counts.",
        mode=AutonomyMode.TEST,
        max_cycles=2,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _authorized_action() -> BoundedActionRecord:
    action = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description="Run tests.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": "run tests"}),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Allowed.",
    )
    return action.with_authority_decision(decision)


def test_state_auditor_does_not_warn_when_dispatched_item_has_matching_result() -> None:
    action = _authorized_action()
    item = ExecutionQueueItem.from_action(action).dispatched()
    result = ForgeResultRecord.from_dispatched_item(
        item=item,
        action=action,
        status=ForgeResultStatus.PASSED,
        summary="Forge execution passed.",
        observed_output="1 passed",
    )
    state = _state().with_action(action).with_execution_queue_item(item).with_forge_result(result)

    report = StateAuditor().audit(state)

    assert not any(
        finding.reference == "execution_queue.dispatched"
        for finding in report.findings
    )
    assert report.ready_for_close() is True
