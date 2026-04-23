"""Safe arithmetic expression evaluator.

Supports the subset of Python needed for PricingConfig.base_formula:
  - variable names (resolved from `env`)
  - numeric literals
  - binary operators: + - * /
  - unary minus
  - parentheses

Everything else (function calls, attribute access, subscripts, comparisons,
imports, comprehensions, ...) raises ValueError. This is deliberately a
small, closed grammar — not a general Python sandbox.
"""
from __future__ import annotations

import ast
from decimal import Decimal
from numbers import Number

_ALLOWED_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
}


def safe_eval(expression: str, env: dict[str, object]) -> Decimal:
    """Evaluate `expression` with names resolved from `env`. Returns Decimal."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"invalid expression syntax: {expression!r}") from e
    return _eval(tree.body, env)


def _eval(node: ast.AST, env: dict[str, object]) -> Decimal:
    if isinstance(node, ast.Constant):
        if not isinstance(node.value, Number) or isinstance(node.value, bool):
            raise ValueError(f"only numeric literals allowed, got {node.value!r}")
        return Decimal(str(node.value))

    if isinstance(node, ast.Name):
        if node.id not in env:
            raise ValueError(f"unknown name in expression: {node.id!r}")
        value = env[node.id]
        if not isinstance(value, Number) or isinstance(value, bool):
            raise ValueError(f"name {node.id!r} bound to non-numeric value")
        return Decimal(str(value))

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval(node.operand, env)

    if isinstance(node, ast.BinOp):
        op_fn = _ALLOWED_BINOPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"operator {type(node.op).__name__} not allowed")
        return op_fn(_eval(node.left, env), _eval(node.right, env))

    raise ValueError(f"AST node {type(node).__name__} not allowed in pricing expression")
