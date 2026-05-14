"""
Evaluador aritmético seguro para fórmulas de KPI.

Permite ÚNICAMENTE:
  - números (int, float)
  - nombres de variables que existan en el contexto
  - operadores binarios: + - * / // % **
  - operadores unarios: + -
  - paréntesis

Cualquier otra cosa (funciones, atributos, importaciones, etc.) levanta ValueError.
"""

import ast
import operator
from decimal import Decimal


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _to_decimal(x):
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def _eval_node(node, variables):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, variables)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return _to_decimal(node.value)
        raise ValueError(f"Constante no permitida: {node.value!r}")
    if isinstance(node, ast.Num):  # py < 3.8 compat
        return _to_decimal(node.n)
    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise ValueError(f"Variable desconocida en la fórmula: '{node.id}'")
        return _to_decimal(variables[node.id])
    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Operador no permitido: {type(node.op).__name__}")
        return op(_eval_node(node.left, variables), _eval_node(node.right, variables))
    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Operador unario no permitido: {type(node.op).__name__}")
        return op(_eval_node(node.operand, variables))
    raise ValueError(f"Elemento no permitido en la fórmula: {type(node).__name__}")


def safe_eval(expression: str, variables: dict) -> Decimal:
    """
    Evalúa `expression` reemplazando los nombres por sus valores en `variables`.
    Devuelve un Decimal. Levanta ValueError si la expresión usa algo no permitido.
    """
    if not expression or not expression.strip():
        raise ValueError("Fórmula vacía.")
    try:
        tree = ast.parse(expression, mode='eval')
    except SyntaxError as e:
        raise ValueError(f"Sintaxis inválida: {e.msg}")
    return _eval_node(tree, variables)


def extract_variable_names(expression: str) -> set:
    """Devuelve los nombres de variable usados en la expresión (útil para validar contra el catálogo)."""
    try:
        tree = ast.parse(expression, mode='eval')
    except SyntaxError:
        return set()
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
