import logging
import os
import uuid
from pathlib import Path
from typing import Any

from agent_framework import MCPStdioTool, MCPStreamableHTTPTool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentMcpServer, McpServer
from app.platform.allowed_tools import mcp_remote_tools_for_server
from app.platform.mcp_config import resolve_runtime_config_safe
from app.platform.profile_loader import mcp_tool_name
from app.platform.secret_store import SecretStoreError

logger = logging.getLogger(__name__)
IS_VERCEL = os.getenv("VERCEL") == "1"
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_NPM_MCP_BINS = {
    "mcp-postgres": "mcp-postgres",
    "mcp-postgres@latest": "mcp-postgres",
    "@benborla29/mcp-server-mysql": "mcp-server-mysql",
    "@benborla29/mcp-server-mysql@latest": "mcp-server-mysql",
}


class McpRegistry:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_servers(self) -> list[McpServer]:
        result = await self._db.execute(select(McpServer).order_by(McpServer.name))
        return list(result.scalars().all())

    async def resolve_for_agent(
        self,
        agent_id: uuid.UUID,
        *,
        agent_config: dict | None = None,
    ) -> list[Any]:
        profile_allowed = list((agent_config or {}).get("allowed_tools") or [])
        result = await self._db.execute(
            select(McpServer)
            .join(AgentMcpServer, AgentMcpServer.mcp_server_id == McpServer.id)
            .where(AgentMcpServer.agent_id == agent_id)
            .order_by(McpServer.name)
        )
        tools: list[Any] = []
        for row in result.scalars().all():
            tool = self._build_tool(row, profile_allowed=profile_allowed)
            if tool is not None:
                tools.append(tool)
        return tools

    def _build_tool(
        self,
        row: McpServer,
        *,
        profile_allowed: list[str] | None = None,
    ) -> MCPStdioTool | MCPStreamableHTTPTool | None:
        try:
            config = resolve_runtime_config_safe(row.connection or {})
        except SecretStoreError:
            logger.exception("MCP server %s has invalid or undecryptable connection", row.name)
            return None

        transport = row.transport or ("http" if config.get("url") else "stdio")
        tool_name = mcp_tool_name(row.name, row.connection)
        description = row.description or f"MCP server: {tool_name}"
        mcp_allowed = mcp_remote_tools_for_server(profile_allowed or [], tool_name)

        if transport == "http" or config.get("url"):
            url = config.get("url")
            if not url:
                logger.warning("MCP server %s missing url", row.name)
                return None
            headers = config.get("headers")
            if headers:
                static_headers = dict(headers)
                return MCPStreamableHTTPTool(
                    name=tool_name,
                    url=url,
                    description=description,
                    allowed_tools=mcp_allowed,
                    header_provider=lambda _kwargs, h=static_headers: dict(h),
                )
            return MCPStreamableHTTPTool(
                name=tool_name,
                url=url,
                description=description,
                allowed_tools=mcp_allowed,
            )

        command = config.get("command")
        if not command:
            logger.warning("MCP server %s missing command", row.name)
            return None
        command, args, env = _resolve_stdio_command_for_runtime(
            str(command),
            list(config.get("args") or []),
            config.get("env"),
        )
        return MCPStdioTool(
            name=tool_name,
            command=command,
            args=args,
            env=env,
            description=description,
            allowed_tools=mcp_allowed,
        )


def _resolve_stdio_command_for_runtime(
    command: str,
    args: list[str],
    env: dict[str, str] | None,
) -> tuple[str, list[str], dict[str, str] | None]:
    """On Vercel, run bundled MCP binaries instead of runtime `npx -y <package>`."""
    if not IS_VERCEL:
        return command, args, env

    if Path(command).name != "npx":
        return command, args, _vercel_child_env(env)

    package_name = _npx_package_name(args)
    bin_name = _NPM_MCP_BINS.get(package_name or "")
    if not bin_name:
        logger.warning("Cannot rewrite npx MCP command on Vercel: args=%s", args)
        return command, args, _vercel_child_env(env)

    bin_path = _BACKEND_ROOT / "node_modules" / ".bin" / bin_name
    if not bin_path.exists():
        logger.warning("Bundled MCP binary missing on Vercel: %s", bin_path)
    logger.info("Rewriting Vercel MCP command npx %s -> %s", package_name, bin_path)
    return str(bin_path), [], _vercel_child_env(env)


def _npx_package_name(args: list[str]) -> str | None:
    for arg in args:
        value = str(arg)
        if value == "-y" or value.startswith("-"):
            continue
        return value
    return None


def _vercel_child_env(env: dict[str, str] | None) -> dict[str, str]:
    merged = dict(env or {})
    node_bin = str(_BACKEND_ROOT / "node_modules" / ".bin")
    merged["PATH"] = f"{node_bin}:{os.environ.get('PATH', '')}"
    merged.setdefault("HOME", "/tmp")
    merged.setdefault("npm_config_cache", "/tmp/.npm")
    return merged
