import os

from app.platform import mcp_registry


def test_vercel_stdio_rewrite_preserves_python_runtime_env(monkeypatch):
    monkeypatch.setattr(mcp_registry, "IS_VERCEL", True)
    monkeypatch.setenv("PYTHONPATH", "/var/task/_vendor")

    command, args, env = mcp_registry._resolve_stdio_command_for_runtime(
        "npx",
        ["-y", "mcp-postgres@latest"],
        {"DATABASE_URL": "postgres://example"},
    )

    assert command
    assert args[-1].endswith("app/mcp_servers/postgres.py")
    assert env is not None
    assert env["DATABASE_URL"] == "postgres://example"
    assert env["PYTHONPATH"] == "/var/task/_vendor"
    assert env["PYTHONUNBUFFERED"] == "1"
