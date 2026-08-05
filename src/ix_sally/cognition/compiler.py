"""Compiler from accepted IX syntax trees into deterministic VM bytecode."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.cognition.bytecode import BytecodeProgram, Instruction, OpCode
from ix_sally.cognition.values import CognitiveValue
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.language.ast import (
    BinaryExpression,
    BinaryOperator,
    Expression,
    GroupExpression,
    LiteralExpression,
    NameExpression,
    UnaryExpression,
    UnaryOperator,
)
from ix_sally.language.frontend import IXFrontendAnalysis, require_accepted_ix_source
from ix_sally.language.statements import (
    AssertStatement,
    LetStatement,
    PrintStatement,
    Program,
    RecallStatement,
    RememberStatement,
    ReplyStatement,
    Statement,
    TraceStatement,
)

_UNARY_OPCODE = {
    UnaryOperator.POSITIVE: OpCode.UNARY_POSITIVE,
    UnaryOperator.NEGATE: OpCode.UNARY_NEGATE,
    UnaryOperator.NOT: OpCode.UNARY_NOT,
}
_BINARY_OPCODE = {
    BinaryOperator.OR: OpCode.BINARY_OR,
    BinaryOperator.AND: OpCode.BINARY_AND,
    BinaryOperator.EQUAL: OpCode.BINARY_EQUAL,
    BinaryOperator.NOT_EQUAL: OpCode.BINARY_NOT_EQUAL,
    BinaryOperator.GREATER: OpCode.BINARY_GREATER,
    BinaryOperator.GREATER_EQUAL: OpCode.BINARY_GREATER_EQUAL,
    BinaryOperator.LESS: OpCode.BINARY_LESS,
    BinaryOperator.LESS_EQUAL: OpCode.BINARY_LESS_EQUAL,
    BinaryOperator.ADD: OpCode.BINARY_ADD,
    BinaryOperator.SUBTRACT: OpCode.BINARY_SUBTRACT,
    BinaryOperator.MULTIPLY: OpCode.BINARY_MULTIPLY,
    BinaryOperator.DIVIDE: OpCode.BINARY_DIVIDE,
}


@dataclass(frozen=True, slots=True)
class IXCompiler:
    """Compile accepted IX programs without evaluating or executing them."""

    def compile_analysis(self, analysis: IXFrontendAnalysis) -> BytecodeProgram:
        """Compile a front-end analysis after requiring it to be accepted."""
        analysis.require_accepted()
        return self.compile_program(
            analysis.program,
            source_digest=analysis.source_digest,
        )

    def compile_program(
        self,
        program: Program,
        *,
        source_digest: DigestRecord,
    ) -> BytecodeProgram:
        """Compile a typed program into a final-halt instruction stream."""
        instructions: list[Instruction] = []
        for statement in program.statements:
            self._compile_statement(statement, instructions=instructions)
        instructions.append(Instruction(OpCode.HALT))
        return BytecodeProgram.create(
            instructions=instructions,
            source_digest=source_digest,
        )

    def _compile_statement(
        self,
        statement: Statement,
        *,
        instructions: list[Instruction],
    ) -> None:
        """Append bytecode for one supported statement."""
        if isinstance(statement, LetStatement):
            self._compile_expression(statement.expression, instructions=instructions)
            instructions.append(Instruction(OpCode.STORE_LOCAL, name=statement.name))
            return
        if isinstance(statement, RememberStatement):
            self._compile_expression(statement.expression, instructions=instructions)
            instructions.append(Instruction(OpCode.STORE_MEMORY, name=statement.name))
            return
        if isinstance(statement, RecallStatement):
            instructions.append(Instruction(OpCode.LOAD_MEMORY, name=statement.name))
            instructions.append(Instruction(OpCode.EMIT_OUTPUT))
            return
        expression_statement: tuple[type[Statement], OpCode] = (
            (PrintStatement, OpCode.EMIT_OUTPUT),
            (ReplyStatement, OpCode.EMIT_REPLY),
            (AssertStatement, OpCode.ASSERT),
            (TraceStatement, OpCode.TRACE),
        )
        for statement_type, opcode in expression_statement:
            if isinstance(statement, statement_type):
                expression = getattr(statement, "expression")
                assert isinstance(expression, Expression)
                self._compile_expression(expression, instructions=instructions)
                instructions.append(Instruction(opcode))
                return
        raise FoundationError(
            f"unsupported IX statement for compilation: {type(statement).__name__}"
        )

    def _compile_expression(
        self,
        expression: Expression,
        *,
        instructions: list[Instruction],
    ) -> None:
        """Append stack-machine bytecode for one expression."""
        if isinstance(expression, LiteralExpression):
            instructions.append(
                Instruction(
                    OpCode.PUSH,
                    value=CognitiveValue.from_python(expression.value),
                )
            )
            return
        if isinstance(expression, NameExpression):
            instructions.append(Instruction(OpCode.LOAD_LOCAL, name=expression.name))
            return
        if isinstance(expression, GroupExpression):
            self._compile_expression(expression.expression, instructions=instructions)
            return
        if isinstance(expression, UnaryExpression):
            self._compile_expression(expression.operand, instructions=instructions)
            instructions.append(Instruction(_UNARY_OPCODE[expression.operator]))
            return
        if isinstance(expression, BinaryExpression):
            self._compile_expression(expression.left, instructions=instructions)
            self._compile_expression(expression.right, instructions=instructions)
            instructions.append(Instruction(_BINARY_OPCODE[expression.operator]))
            return
        raise FoundationError(
            f"unsupported IX expression for compilation: {type(expression).__name__}"
        )


def compile_ix_source(
    source: str,
    *,
    filename: str = "<memory>",
) -> BytecodeProgram:
    """Analyze and compile one IX source document."""
    return IXCompiler().compile_analysis(
        require_accepted_ix_source(source, filename=filename)
    )
