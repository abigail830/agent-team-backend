"""Pre-tool SQL validation — MAF equivalent of Claude Agent SDK PreToolUse hook."""

from __future__ import annotations

from typing import Any

from agent_framework import FunctionInvocationContext, FunctionMiddleware, MiddlewareTermination
from pydantic import BaseModel

from app.guardrails.sql_rules import validate_sql
from app.middleware.sql_tools import is_sql_run_query


def _extract_query(arguments: Any) -> str | None:
    if isinstance(arguments, dict):
        value = arguments.get("query")
        return str(value) if value is not None else None
    if isinstance(arguments, BaseModel):
        value = getattr(arguments, "query", None)
        return str(value) if value is not None else None
    return None


def _apply_query(arguments: Any, query: str) -> Any:
    if isinstance(arguments, dict):
        updated = dict(arguments)
        updated["query"] = query
        return updated
    if isinstance(arguments, BaseModel):
        return arguments.model_copy(update={"query": query})
    return arguments


class SqlValidatorMiddleware(FunctionMiddleware):
    """Deny or rewrite SQL run_query calls (postgres / mysql) using guardrails.sql rules."""

    def __init__(self, *, max_rows: int = 2000) -> None:
        self._max_rows = max_rows

    async def process(self, context: FunctionInvocationContext, call_next) -> None:
        tool_name = context.function.name
        if not is_sql_run_query(tool_name):
            await call_next()
            return

        query = _extract_query(context.arguments)
        if query is None:
            context.result = {"error": "Missing required argument: query"}
            raise MiddlewareTermination("SQL validator blocked tool: missing query")

        result = validate_sql(query, max_rows=self._max_rows)
        if not result.ok:
            context.result = {"error": result.reason, "function": tool_name}
            raise MiddlewareTermination(f"SQL validation denied: {result.reason}")

        if result.normalized_sql != query:
            context.arguments = _apply_query(context.arguments, result.normalized_sql)

        await call_next()
