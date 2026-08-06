"""Bounded deterministic virtual machine for compiled IX programs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.cognition.bytecode import BytecodeProgram, Instruction, OpCode
from ix_sally.cognition.values import CognitiveValue, CognitiveValueType
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import FoundationError


class VMStatus(StrEnum):
    """Terminal status of one bounded VM run."""

    HALTED = "halted"
    FAILED = "failed"
    STEP_LIMIT = "step_limit"


@dataclass(frozen=True, slots=True)
class VMTraceEntry:
    """One instruction-level execution receipt."""

    step: int
    instruction_pointer: int
    opcode: OpCode
    stack_depth_before: int
    stack_depth_after: int

    def to_payload(self) -> JsonObject:
        """Return a stable trace payload."""
        return {
            "step": self.step,
            "instruction_pointer": self.instruction_pointer,
            "opcode": self.opcode.value,
            "stack_depth_before": self.stack_depth_before,
            "stack_depth_after": self.stack_depth_after,
        }


@dataclass(frozen=True, slots=True)
class VMResult:
    """Complete immutable receipt from one IX bytecode execution."""

    status: VMStatus
    program_digest: DigestRecord
    steps: int
    local_values: tuple[tuple[str, CognitiveValue], ...]
    memories: tuple[tuple[str, CognitiveValue], ...]
    outputs: tuple[CognitiveValue, ...]
    replies: tuple[CognitiveValue, ...]
    traces: tuple[CognitiveValue, ...]
    instruction_trace: tuple[VMTraceEntry, ...]
    failure: str | None = None

    def __post_init__(self) -> None:
        """Require terminal status and failure detail to agree."""
        self.program_digest.require_algorithm("sha256")
        if self.steps < 0:
            raise FoundationError("VM result steps must not be negative")
        if self.status is VMStatus.HALTED and self.failure is not None:
            raise FoundationError("halted VM result must not contain a failure")
        if self.status is not VMStatus.HALTED and not self.failure:
            raise FoundationError("non-halted VM result requires failure detail")

    def local_map(self) -> dict[str, CognitiveValue]:
        """Return a defensive local-value mapping."""
        return dict(self.local_values)

    def memory_map(self) -> dict[str, CognitiveValue]:
        """Return a defensive memory-value mapping."""
        return dict(self.memories)

    def to_payload(self) -> JsonObject:
        """Return a deterministic receipt payload."""
        local_values: JsonArray = [
            {"name": name, "value": value.to_payload()} for name, value in self.local_values
        ]
        memory_values: JsonArray = [
            {"name": name, "value": value.to_payload()} for name, value in self.memories
        ]
        outputs: JsonArray = [value.to_payload() for value in self.outputs]
        replies: JsonArray = [value.to_payload() for value in self.replies]
        traces: JsonArray = [value.to_payload() for value in self.traces]
        instruction_trace: JsonArray = [entry.to_payload() for entry in self.instruction_trace]
        return {
            "status": self.status.value,
            "program_digest": {
                "algorithm": self.program_digest.algorithm,
                "value": self.program_digest.value,
            },
            "steps": self.steps,
            "locals": local_values,
            "memories": memory_values,
            "outputs": outputs,
            "replies": replies,
            "traces": traces,
            "instruction_trace": instruction_trace,
            "failure": self.failure,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic identity for this execution."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class IXVirtualMachine:
    """Execute bytecode with no I/O, imports, callbacks, or arbitrary code."""

    max_steps: int = 10_000

    def __post_init__(self) -> None:
        """Require a positive execution budget."""
        if self.max_steps <= 0:
            raise FoundationError("VM max_steps must be positive")

    def execute(
        self,
        program: BytecodeProgram,
        *,
        initial_locals: Mapping[str, CognitiveValue] | None = None,
        memories: Mapping[str, CognitiveValue] | None = None,
    ) -> VMResult:
        """Execute one program and return a receipt instead of raising runtime faults."""
        local_values = dict(initial_locals or {})
        memory_values = dict(memories or {})
        stack: list[CognitiveValue] = []
        outputs: list[CognitiveValue] = []
        replies: list[CognitiveValue] = []
        traces: list[CognitiveValue] = []
        instruction_trace: list[VMTraceEntry] = []
        pointer = 0
        steps = 0

        while pointer < len(program.instructions):
            if steps >= self.max_steps:
                return self._result(
                    status=VMStatus.STEP_LIMIT,
                    program=program,
                    steps=steps,
                    local_values=local_values,
                    memories=memory_values,
                    outputs=outputs,
                    replies=replies,
                    traces=traces,
                    instruction_trace=instruction_trace,
                    failure=f"execution exceeded step limit {self.max_steps}",
                )
            instruction = program.instructions[pointer]
            depth_before = len(stack)
            try:
                halted = self._execute_instruction(
                    instruction,
                    stack=stack,
                    local_values=local_values,
                    memories=memory_values,
                    outputs=outputs,
                    replies=replies,
                    traces=traces,
                )
            except (FoundationError, ZeroDivisionError) as exc:
                return self._result(
                    status=VMStatus.FAILED,
                    program=program,
                    steps=steps + 1,
                    local_values=local_values,
                    memories=memory_values,
                    outputs=outputs,
                    replies=replies,
                    traces=traces,
                    instruction_trace=instruction_trace,
                    failure=f"instruction {pointer} {instruction.opcode.value}: {exc}",
                )
            steps += 1
            instruction_trace.append(
                VMTraceEntry(
                    step=steps,
                    instruction_pointer=pointer,
                    opcode=instruction.opcode,
                    stack_depth_before=depth_before,
                    stack_depth_after=len(stack),
                )
            )
            if halted:
                return self._result(
                    status=VMStatus.HALTED,
                    program=program,
                    steps=steps,
                    local_values=local_values,
                    memories=memory_values,
                    outputs=outputs,
                    replies=replies,
                    traces=traces,
                    instruction_trace=instruction_trace,
                )
            pointer += 1

        return self._result(
            status=VMStatus.FAILED,
            program=program,
            steps=steps,
            local_values=local_values,
            memories=memory_values,
            outputs=outputs,
            replies=replies,
            traces=traces,
            instruction_trace=instruction_trace,
            failure="program terminated without halt",
        )

    def _execute_instruction(
        self,
        instruction: Instruction,
        *,
        stack: list[CognitiveValue],
        local_values: dict[str, CognitiveValue],
        memories: dict[str, CognitiveValue],
        outputs: list[CognitiveValue],
        replies: list[CognitiveValue],
        traces: list[CognitiveValue],
    ) -> bool:
        """Execute one instruction and return whether it halted the VM."""
        opcode = instruction.opcode
        if opcode is OpCode.HALT:
            return True
        if opcode is OpCode.PUSH:
            assert instruction.value is not None
            stack.append(instruction.value)
            return False
        if opcode is OpCode.LOAD_LOCAL:
            assert instruction.name is not None
            stack.append(self._require_name(local_values, instruction.name, namespace="local"))
            return False
        if opcode is OpCode.STORE_LOCAL:
            assert instruction.name is not None
            local_values[instruction.name] = self._pop(stack, operation=opcode.value)
            return False
        if opcode is OpCode.LOAD_MEMORY:
            assert instruction.name is not None
            stack.append(self._require_name(memories, instruction.name, namespace="memory"))
            return False
        if opcode is OpCode.STORE_MEMORY:
            assert instruction.name is not None
            memories[instruction.name] = self._pop(stack, operation=opcode.value)
            return False
        if opcode in {
            OpCode.UNARY_POSITIVE,
            OpCode.UNARY_NEGATE,
            OpCode.UNARY_NOT,
        }:
            stack.append(self._unary(opcode, self._pop(stack, operation=opcode.value)))
            return False
        if opcode.value.startswith("binary_"):
            right = self._pop(stack, operation=opcode.value)
            left = self._pop(stack, operation=opcode.value)
            stack.append(self._binary(opcode, left, right))
            return False
        value = self._pop(stack, operation=opcode.value)
        if opcode is OpCode.EMIT_OUTPUT:
            outputs.append(value)
            return False
        if opcode is OpCode.EMIT_REPLY:
            replies.append(value)
            return False
        if opcode is OpCode.TRACE:
            traces.append(value)
            return False
        if opcode is OpCode.ASSERT:
            if not value.require_boolean(operation="assert"):
                raise FoundationError("assertion evaluated to false")
            return False
        raise FoundationError(f"unsupported VM opcode: {opcode.value}")

    def _unary(self, opcode: OpCode, value: CognitiveValue) -> CognitiveValue:
        """Evaluate one unary operation without silent coercion."""
        if opcode is OpCode.UNARY_NOT:
            return CognitiveValue.from_python(not value.require_boolean(operation=opcode.value))
        number = value.require_numeric(operation=opcode.value)
        if opcode is OpCode.UNARY_POSITIVE:
            return CognitiveValue.from_python(+number)
        return CognitiveValue.from_python(-number)

    def _binary(
        self,
        opcode: OpCode,
        left: CognitiveValue,
        right: CognitiveValue,
    ) -> CognitiveValue:
        """Evaluate one binary operation under exact runtime type rules."""
        if opcode is OpCode.BINARY_EQUAL:
            return CognitiveValue.from_python(
                left.value_type is right.value_type and left.value == right.value
            )
        if opcode is OpCode.BINARY_NOT_EQUAL:
            return CognitiveValue.from_python(
                left.value_type is not right.value_type or left.value != right.value
            )
        if opcode in {OpCode.BINARY_OR, OpCode.BINARY_AND}:
            left_bool = left.require_boolean(operation=opcode.value)
            right_bool = right.require_boolean(operation=opcode.value)
            result = left_bool or right_bool
            if opcode is OpCode.BINARY_AND:
                result = left_bool and right_bool
            return CognitiveValue.from_python(result)
        if opcode is OpCode.BINARY_ADD and (
            left.value_type is CognitiveValueType.STRING
            or right.value_type is CognitiveValueType.STRING
        ):
            if left.value_type is not right.value_type:
                raise FoundationError("string addition requires two strings")
            assert isinstance(left.value, str)
            assert isinstance(right.value, str)
            return CognitiveValue.from_python(left.value + right.value)
        left_number = left.require_numeric(operation=opcode.value)
        right_number = right.require_numeric(operation=opcode.value)
        if opcode is OpCode.BINARY_ADD:
            return CognitiveValue.from_python(left_number + right_number)
        if opcode is OpCode.BINARY_SUBTRACT:
            return CognitiveValue.from_python(left_number - right_number)
        if opcode is OpCode.BINARY_MULTIPLY:
            return CognitiveValue.from_python(left_number * right_number)
        if opcode is OpCode.BINARY_DIVIDE:
            if right_number == 0:
                raise ZeroDivisionError("division by zero")
            return CognitiveValue.from_python(left_number / right_number)
        if opcode is OpCode.BINARY_GREATER:
            return CognitiveValue.from_python(left_number > right_number)
        if opcode is OpCode.BINARY_GREATER_EQUAL:
            return CognitiveValue.from_python(left_number >= right_number)
        if opcode is OpCode.BINARY_LESS:
            return CognitiveValue.from_python(left_number < right_number)
        if opcode is OpCode.BINARY_LESS_EQUAL:
            return CognitiveValue.from_python(left_number <= right_number)
        raise FoundationError(f"unsupported binary opcode: {opcode.value}")

    def _pop(self, stack: list[CognitiveValue], *, operation: str) -> CognitiveValue:
        """Pop one stack value or report deterministic underflow."""
        if not stack:
            raise FoundationError(f"stack underflow during {operation}")
        return stack.pop()

    def _require_name(
        self,
        values: Mapping[str, CognitiveValue],
        name: str,
        *,
        namespace: str,
    ) -> CognitiveValue:
        """Return one bound value or fail closed."""
        try:
            return values[name]
        except KeyError as exc:
            raise FoundationError(f"unknown {namespace} name: {name}") from exc

    def _result(
        self,
        *,
        status: VMStatus,
        program: BytecodeProgram,
        steps: int,
        local_values: Mapping[str, CognitiveValue],
        memories: Mapping[str, CognitiveValue],
        outputs: list[CognitiveValue],
        replies: list[CognitiveValue],
        traces: list[CognitiveValue],
        instruction_trace: list[VMTraceEntry],
        failure: str | None = None,
    ) -> VMResult:
        """Create a stable terminal VM result."""
        return VMResult(
            status=status,
            program_digest=program.digest(),
            steps=steps,
            local_values=tuple(sorted(local_values.items())),
            memories=tuple(sorted(memories.items())),
            outputs=tuple(outputs),
            replies=tuple(replies),
            traces=tuple(traces),
            instruction_trace=tuple(instruction_trace),
            failure=failure,
        )
