"""
Real MCP client for fraud-agent-service.

Replaces the earlier version of this file, which faked "MCP" by wrapping
plain requests.get()/post() calls in LangChain @tool decorators. This
version uses langchain-mcp-adapters' MultiServerMCPClient, which speaks
actual MCP protocol (tool discovery + typed schemas + invocation) to the
fraud-mcp-server built in app/server.py.

Because tools are *discovered* rather than hand-declared, adding a new
tool to fraud-mcp-server (e.g. a `device_fingerprint_check` tool) makes
it available here automatically — no code change needed in the agent.

Auth note: tools are discovered once at startup (see app/agent.py), but
the service-account token used to call fraud-mcp-server expires every
few minutes. A static header set at discovery time would go stale
mid-investigation. To avoid that, a tool_interceptor re-fetches a fresh
token and injects it into the headers on every single tool call, not
just at connection time.
"""

import os

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.interceptors import MCPToolCallRequest

from app.token_manager import get_service_token

MCP_SERVER_URL = os.getenv(
    "MCP_SERVER_URL",
    "http://fraud-mcp-server:9000/mcp",
)


async def _inject_fresh_token(request: MCPToolCallRequest, handler):
    """Tool call interceptor: attaches a current bearer token to every
    outgoing MCP tool call, refreshing it transparently as needed."""
    token = await get_service_token()
    updated_request = request.override(
        headers={**(request.headers or {}), "Authorization": f"Bearer {token}"}
    )
    return await handler(updated_request)


_client = MultiServerMCPClient(
    {
        "fraud_mcp_server": {
            "url": MCP_SERVER_URL,
            "transport": "streamable_http",
        }
    },
    tool_interceptors=[_inject_fresh_token],
)


async def get_tools():
    """
    Discover and return the live tool list from the MCP server.
    Call this once at startup (see app/agent.py) rather than per-request.
    Each returned tool will attach a fresh bearer token on every call,
    regardless of how long ago discovery happened.
    """
    return await _client.get_tools()