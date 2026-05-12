"""MCP Client — Agent-side client for calling tools via MCP protocol.

When an agent wants to call a tool through MCP instead of direct function call,
it uses this client. This enables:
1. Tool discovery — agent can list available tools at runtime
2. Protocol-standard interface — same protocol as VS Code, Claude, etc.
3. Remote tool execution — tools can run on a different process/machine
4. Access control — MCP transport layer handles auth

Usage:
    client = MCPClient("http://localhost:8000/mcp/")
    tools = await client.list_tools()
    result = await client.call_tool("search_knowledge", {"query": "HIPAA policy"})
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


class MCPClient:
    """Lightweight MCP client for streamable-http transport.

    Implements the minimal MCP JSON-RPC subset needed for tool calling:
    - tools/list — discover available tools
    - tools/call — execute a tool with arguments
    """

    def __init__(self, base_url: str = "http://localhost:8000/mcp/"):
        self._base_url = base_url.rstrip("/")
        self._session_id: str | None = None
        self._http: httpx.AsyncClient | None = None

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=60.0)
        return self._http

    async def _rpc(self, method: str, params: dict | None = None) -> Any:
        """Send a JSON-RPC 2.0 request over HTTP."""
        http = await self._get_http()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
        }
        if params:
            payload["params"] = params

        headers = {"Content-Type": "application/json"}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        response = await http.post(self._base_url, json=payload, headers=headers)
        response.raise_for_status()

        # Capture session ID from response headers
        if "Mcp-Session-Id" in response.headers:
            self._session_id = response.headers["Mcp-Session-Id"]

        data = response.json()
        if "error" in data:
            raise MCPError(data["error"].get("message", "Unknown MCP error"))
        return data.get("result")

    async def initialize(self) -> dict:
        """Initialize MCP session (required before other calls)."""
        result = await self._rpc("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "enterprise-genai-agent", "version": "0.2.0"},
        })
        logger.info("mcp_client.initialized", server=self._base_url)
        # Send initialized notification
        await self._notify("notifications/initialized")
        return result

    async def _notify(self, method: str, params: dict | None = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        http = await self._get_http()
        payload = {"jsonrpc": "2.0", "method": method}
        if params:
            payload["params"] = params
        headers = {"Content-Type": "application/json"}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        await http.post(self._base_url, json=payload, headers=headers)

    async def list_tools(self) -> list[dict]:
        """Discover available tools from the MCP server.

        Returns list of tool schemas compatible with OpenAI function-calling format.
        """
        result = await self._rpc("tools/list")
        tools = result.get("tools", [])
        logger.info("mcp_client.tools_listed", count=len(tools))
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on the MCP server.

        Args:
            name: Tool name (e.g., "search_knowledge")
            arguments: Tool arguments as a dict

        Returns:
            Tool result as a string
        """
        result = await self._rpc("tools/call", {
            "name": name,
            "arguments": arguments,
        })
        # MCP returns content as array of content blocks
        content_blocks = result.get("content", [])
        texts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
        output = "\n".join(texts)
        logger.info("mcp_client.tool_called", tool=name, output_len=len(output))
        return output

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None


class MCPError(Exception):
    """Error from MCP server."""
    pass
