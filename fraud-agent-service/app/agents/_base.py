"""
Shared plumbing for the domain-specialist agents.

Each specialist is a ReAct agent scoped to only the MCP tool(s) it needs
(unlike app/agent.py's single agent, which is handed every tool at once).
This module centralizes the "discover tools, filter to the ones this
specialist owns, lazily build + cache a react agent, wrap it as a graph
node that reports back to the supervisor" logic so each agent file only
has to declare its name, tool(s), and system prompt.
"""

import logging
import os

from langgraph.graph import MessagesState
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command

from app.mcp_client import get_tools
from app import get_llm

logger = logging.getLogger(__name__)
llm = get_llm()


def make_specialist(agent_name: str, tool_names: list[str], system_prompt: str):
    """
    Build a (get_agent, node) pair for a specialist scoped to `tool_names`.

    get_agent() lazily discovers the live MCP tool list and filters it down
    to just this specialist's tool(s), then compiles + caches a ReAct agent.

    node(state) invokes that agent on the running conversation, tags the
    resulting message with this specialist's name (so the supervisor and
    other agents can tell who said what), and hands control back to the
    supervisor node for the next routing decision.
    """
    _agent = {"instance": None}

    async def get_agent():
        if _agent["instance"] is None:
            tools = await get_tools()
            scoped_tools = [t for t in tools if t.name in tool_names]
            missing = set(tool_names) - {t.name for t in scoped_tools}
            if missing:
                raise RuntimeError(
                    f"{agent_name}: expected MCP tool(s) {sorted(missing)} "
                    "not found on fraud-mcp-server"
                )
            _agent["instance"] = create_react_agent(
                llm, scoped_tools, prompt=system_prompt
            )
        return _agent["instance"]

    async def node(state: MessagesState) -> Command:
        agent = await get_agent()
        result = await agent.ainvoke(state)
        last_message = result["messages"][-1]

        # Phase 5: Log cache-hit metrics if available
        token_usage = result.get("response_metadata", {}).get("token_usage", {})
        cached_tokens = token_usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
        if cached_tokens:
            logger.info(
                "%s cache hit: %s cached / %s total tokens",
                agent_name,
                cached_tokens,
                token_usage.get("prompt_tokens", 0),
            )

        return Command(
            update={
                "messages": [
                    {
                        "role": "assistant",
                        "content": last_message.content,
                        "name": agent_name,
                    }
                ]
            },
            goto="supervisor",
        )

    return get_agent, node