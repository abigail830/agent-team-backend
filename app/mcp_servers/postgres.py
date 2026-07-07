from __future__ import annotations

import asyncio
import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

import asyncpg
from mcp.server.fastmcp import FastMCP

SERVER = FastMCP("postgres")
MAX_ROWS = int(os.getenv("MCP_MAX_ROWS", "2000"))


def _database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is required")
    return value


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _json_result(value: Any) -> str:
    return json.dumps(value, default=_json_default, ensure_ascii=False)


def _readonly_query(sql: str) -> str:
    query = sql.strip().rstrip(";")
    if ";" in query:
        raise ValueError("Only one read-only SQL statement is allowed")
    lowered = query.lower().lstrip("(\n\t ")
    if not lowered.startswith(("select", "with", "explain")):
        raise ValueError("Only read-only SELECT/WITH/EXPLAIN queries are allowed")
    return query


def _limited_query(query: str, limit: int) -> str:
    lowered = query.lower().lstrip("(\n\t ")
    if lowered.startswith(("select", "with")):
        return f"select * from ({query}) as _mcp_query limit {limit}"
    return query


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(_database_url())


@SERVER.tool(name="list_tables", description="List tables and views in the database.")
async def list_tables(schema: str = "public") -> str:
    conn = await _connect()
    try:
        rows = await conn.fetch(
            """
            select table_schema, table_name, table_type
            from information_schema.tables
            where table_schema = $1
            order by table_schema, table_name
            """,
            schema,
        )
        return _json_result({"tables": [dict(row) for row in rows]})
    finally:
        await conn.close()


@SERVER.tool(name="describe_table", description="Describe columns for a table.")
async def describe_table(table_name: str, schema: str = "public") -> str:
    conn = await _connect()
    try:
        rows = await conn.fetch(
            """
            select column_name, data_type, is_nullable, column_default
            from information_schema.columns
            where table_schema = $1 and table_name = $2
            order by ordinal_position
            """,
            schema,
            table_name,
        )
        return _json_result(
            {"schema": schema, "table": table_name, "columns": [dict(row) for row in rows]}
        )
    finally:
        await conn.close()


@SERVER.tool(name="get_schema", description="Return table and column schema metadata.")
async def get_schema(schema: str = "public") -> str:
    conn = await _connect()
    try:
        rows = await conn.fetch(
            """
            select table_name, column_name, data_type, is_nullable
            from information_schema.columns
            where table_schema = $1
            order by table_name, ordinal_position
            """,
            schema,
        )
        tables: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            item = dict(row)
            table = item.pop("table_name")
            tables.setdefault(table, []).append(item)
        return _json_result({"schema": schema, "tables": tables})
    finally:
        await conn.close()


@SERVER.tool(name="query_data", description="Execute a read-only SQL query.")
async def query_data(query: str, max_rows: int = MAX_ROWS) -> str:
    readonly = _readonly_query(query)
    limit = max(1, min(int(max_rows or MAX_ROWS), MAX_ROWS))
    sql = _limited_query(readonly, limit)
    conn = await _connect()
    try:
        async with conn.transaction():
            await conn.execute("set transaction read only")
            rows = await conn.fetch(sql, timeout=30)
        return _json_result({"row_count": len(rows), "rows": [dict(row) for row in rows]})
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(SERVER.run_stdio_async())
