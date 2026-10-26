"""Pure tool logic with no I/O: allowlisted pandas statistics and an AST-whitelist calculator.

Rule 8: nothing here uses eval, exec or DataFrame.query. Anything outside the allowlists raises ToolError.
"""
from __future__ import annotations

import ast
import json
import math
import operator
from typing import Any, Callable

import pandas as pd

from src import config


class ToolError(ValueError):
    """Bad arguments or an expected failure. The message is shown to the model."""


ANALYSIS_OPS: tuple[str, ...] = ("count", "churn_rate", "mean", "median", "sum", "min", "max", "value_counts")
NUMERIC_OPS = frozenset({"mean", "median", "sum", "min", "max"})
FILTER_OPS: dict[str, Callable[[Any, Any], Any]] = {
    "==": operator.eq, "!=": operator.ne, ">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le,
}
_BIN_OPS: dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Mod: operator.mod,
}
_UNARY_OPS: dict[type, Callable[[Any], Any]] = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _num(value: Any) -> int | float | None:
    """numpy/pandas scalar -> plain Python number (floats rounded, NaN -> None)."""
    number = value.item() if hasattr(value, "item") else value
    if isinstance(number, float):
        return None if math.isnan(number) else round(number, 4)
    return number


def _rate(mean: Any, n: Any) -> dict[str, Any]:
    """Churn rate as a fraction and as a percent, so the model can quote either exactly."""
    return {"churn_rate": _num(mean), "percent": _num(float(mean) * 100), "customers": int(n)}


def _check_column(frame: pd.DataFrame, name: Any, label: str) -> str:
    if not isinstance(name, str) or name not in frame.columns:
        raise ToolError(f"unknown {label} {name!r}; valid columns: {list(frame.columns)}")
    return name


def _apply_filters(frame: pd.DataFrame, filters: Any) -> pd.DataFrame:
    """Apply validated column/op/value filters. Value type must match the column (no silent mismatches)."""
    if not isinstance(filters, list) or len(filters) > config.AGENT_MAX_FILTERS:
        raise ToolError(f"'filters' must be a list of at most {config.AGENT_MAX_FILTERS} objects")
    for item in filters:
        if not isinstance(item, dict):
            raise ToolError("each filter must be an object with column, op and value")
        column = _check_column(frame, item.get("column"), "filter column")
        op, value = item.get("op"), item.get("value")
        if not isinstance(op, str) or op not in FILTER_OPS:
            raise ToolError(f"filter op must be one of {list(FILTER_OPS)}")
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ToolError("filter value must be a number or a string")
        numeric = pd.api.types.is_numeric_dtype(frame[column])
        if numeric != isinstance(value, (int, float)):
            raise ToolError(f"column {column!r} is {'numeric' if numeric else 'text'}; use a matching value")
        if not numeric and op not in ("==", "!="):
            raise ToolError(f"text column {column!r} supports only == and !=")
        frame = frame[FILTER_OPS[op](frame[column], value)]
    return frame


def analyze_frame(frame: pd.DataFrame, args: dict[str, Any]) -> str:
    """Run one allowlisted statistic. Returns a JSON string; raises ToolError on any bad argument."""
    op = args.get("operation")
    if not isinstance(op, str) or op not in ANALYSIS_OPS:
        raise ToolError(f"operation must be one of {list(ANALYSIS_OPS)}")
    column, group_by = args.get("column"), args.get("group_by")
    if column is not None:
        _check_column(frame, column, "column")
    if group_by is not None:
        _check_column(frame, group_by, "group_by")
    filters = args.get("filters") or []
    rows = _apply_filters(frame, filters)
    if op in NUMERIC_OPS and (column is None or not pd.api.types.is_numeric_dtype(frame[column])):
        raise ToolError(f"{op} needs a numeric 'column'")
    if op == "value_counts" and (column is None or group_by is not None):
        raise ToolError("value_counts needs 'column' and does not take group_by")
    limit, truncated, result = config.AGENT_MAX_ROWS, False, None
    if rows.empty:
        pass
    elif op == "count":
        result = len(rows) if group_by is None else rows.groupby(group_by).size()
    elif op == "churn_rate":
        churned = rows[config.TARGET_COL].eq("Yes")
        if group_by is None:
            result = _rate(churned.mean(), len(rows))
        else:
            grouped = churned.groupby(rows[group_by]).agg(["mean", "size"])
            truncated = len(grouped) > limit
            result = {str(k): _rate(r["mean"], r["size"]) for k, r in grouped.head(limit).iterrows()}
    elif op == "value_counts":
        result = rows[column].value_counts()
    else:  # mean / median / sum / min / max, op is allowlisted above
        result = rows[column].agg(op) if group_by is None else rows.groupby(group_by)[column].agg(op)
    if isinstance(result, pd.Series):
        truncated = len(result) > limit
        result = {str(k): _num(v) for k, v in result.head(limit).items()}
    elif result is not None and not isinstance(result, dict):
        result = _num(result)
    payload: dict[str, Any] = {
        "operation": op, "column": column, "group_by": group_by, "filters": filters,
        "rows_used": len(rows), "result": result, "truncated": truncated,
    }
    if rows.empty:
        payload["note"] = "no rows match the filters"
    return json.dumps(payload, default=str)


def _eval_node(node: ast.AST) -> int | float:
    """Walk only whitelisted node types: numbers, + - * / %, unary +/-. Everything else is rejected."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise ToolError("only numbers, + - * / % and parentheses are allowed (write 30% as 30/100)")


def _format_number(value: int | float) -> str:
    if not math.isfinite(value):
        raise ValueError("not finite")
    if isinstance(value, float):
        return format(round(value, 6), "f").rstrip("0").rstrip(".")
    return str(value)


def safe_calculate(expression: str) -> str:
    """Evaluate plain arithmetic. Returns 'expression = value'. No exponent operator on purpose."""
    expression = expression.strip()
    if len(expression) > config.AGENT_CALC_MAX_CHARS:
        raise ToolError(f"expression is longer than {config.AGENT_CALC_MAX_CHARS} characters")
    try:
        text = _format_number(_eval_node(ast.parse(expression, mode="eval")))
    except ToolError:
        raise
    except SyntaxError as exc:
        raise ToolError(f"not a valid arithmetic expression: {exc.msg}") from exc
    except ZeroDivisionError as exc:
        raise ToolError("division by zero") from exc
    except (OverflowError, ValueError) as exc:
        raise ToolError("result is not a usable number") from exc
    return f"{expression} = {text}"