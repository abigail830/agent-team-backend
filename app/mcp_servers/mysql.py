from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Any

import pymysql
from mcp.server.fastmcp import FastMCP

SERVER = FastMCP("mysql")
MAX_ROWS = int(os.getenv("MCP_MAX_ROWS", "2000"))


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _json_result(value: Any) -> str:
    return json.dumps(value, default=_json_default, ensure_ascii=False)


def _readonly_query(sql: str) -> str:
    query = sql.strip().rstrip(";")
    if ";" in query:
        raise ValueError("Only one read-only SQL statement is allowed")
    lowered = query.lower().lstrip("(\n\t ")
    if not lowered.startswith(("select", "with", "show", "describe", "explain")):
        raise ValueError("Only read-only SQL queries are allowed")
    return query


def _limited_query(query: str, limit: int) -> str:
    lowered = query.lower().lstrip("(\n\t ")
    if lowered.startswith(("select", "with")):
        return f"select * from ({query}) as _mcp_query limit {limit}"
    return query


def _connect() -> pymysql.connections.Connection:
    ssl = {"ssl": {}} if os.getenv("MYSQL_SSL", "").lower() in {"1", "true", "yes"} else {}
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASS"),
        database=os.getenv("MYSQL_DB") or None,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=30,
        write_timeout=30,
        autocommit=False,
        **ssl,
    )


@SERVER.tool(name="mysql_query", description="Execute a read-only MySQL query.")
def mysql_query(query: str, max_rows: int = MAX_ROWS) -> str:
    readonly = _readonly_query(query)
    limit = max(1, min(int(max_rows or MAX_ROWS), MAX_ROWS))
    sql = _limited_query(readonly, limit)
    conn = _connect()
    try:
        with conn.cursor() as cursor:
            cursor.execute("start transaction read only")
            cursor.execute(sql)
            rows = cursor.fetchall()
            cursor.execute("rollback")
        return _json_result({"row_count": len(rows), "rows": rows})
    finally:
        conn.close()


if __name__ == "__main__":
    SERVER.run()
