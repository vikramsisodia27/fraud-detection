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
"""

import os

from langchain_mcp_adapters.client import MultiServerMCPClient

MCP_SERVER_URL = os.getenv(
    "MCP_SERVER_URL",
    "http://fraud-mcp-server:9000/mcp",
)

_client = MultiServerMCPClient(
    {
        "fraud_mcp_server": {
            "url": MCP_SERVER_URL,
            "transport": "streamable_http",
        }
    }
)


async def get_tools():
    """
    Discover and return the live tool list from the MCP server.
    Call this once at startup (see app/agent.py) rather than per-request.
    """
    return await _client.get_tools()