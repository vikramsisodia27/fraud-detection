"""
True multi-agent supervisor for the fraud investigation team.

app/agent.py's `investigate_fraud` is a single ReAct agent that has every
MCP tool (bureau_check, aml_check, customer_context, create_case) bolted
on at once. That file is left untouched and still works standalone.

This module is an enhancement layered on top: an actual supervisor/worker
graph, where a router LLM decides — turn by turn — which domain specialist
should act next, and each specialist (app/agents/*) is its own agent that
can only see the one tool relevant to its role. This gives real separation
of concerns (a bureau-check bug can't accidentally touch case creation),
clearer per-step reasoning traces, and an easy place to add new
specialists later without touching the others.
"""

import json
import logging
import re
from typing import TypedDict, Literal

from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.types import Command

from app import get_llm
from app.agents import bureau_node, aml_node, compliance_node, case_node

logger = logging.getLogger(__name__)

MEMBERS = ["bureau_agent", "aml_agent", "compliance_agent", "case_agent"]
OPTIONS = MEMBERS + ["FINISH"]

SUPERVISOR_BASE = """You are the supervisor of a fraud-investigation team. You do not call any tools yourself — you only decide, at each step, which specialist should act next.

AVAILABLE SPECIALISTS:
- bureau_agent: Runs a credit bureau / delinquency check via the `bureau_check` tool.
- aml_agent: Runs an AML / sanctions screening check via the `aml_check` tool.
- compliance_agent: Retrieves historical customer context (past fraud cases, SAR reports, KYC documents, analyst notes) via the `customer_context` tool (RAG over vector store).
- case_agent: Creates the final investigation case record via the `create_case` tool. Must run LAST, only after bureau_agent, aml_agent, and compliance_agent have all reported results.

ROUTING RULES:
1. Always start with bureau_agent or aml_agent (order doesn't matter).
2. Run compliance_agent after bureau and AML have reported.
3. Run case_agent LAST, after all three specialists have reported.
4. Once case_agent has created the case and reported the case ID, respond with FINISH.

You MUST respond with valid JSON only, using EXACTLY this format:
{"next": "bureau_agent"}
Possible values for "next": bureau_agent, aml_agent, compliance_agent, case_agent, FINISH"""


class Router(TypedDict):
    """Structured routing decision."""
    next: Literal["bureau_agent", "aml_agent", "compliance_agent", "case_agent", "FINISH"]


llm = get_llm()


def _parse_next(raw: str) -> str:
    """Extract the routing decision from raw LLM output using JSON parsing."""
    # Try to parse as JSON first
    text = raw.strip()
    # Remove markdown code fences if present
    text = re.sub(r'^```(?:json)?\s*|```\s*$', '', text, flags=re.MULTILINE)
    text = text.strip()

    # Try JSON parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "next" in parsed:
            return parsed["next"]
    except json.JSONDecodeError:
        pass

    # Fallback: look for one of the valid tokens directly in the text
    for option in ["FINISH", "case_agent", "compliance_agent", "aml_agent", "bureau_agent"]:
        if option in text:
            return option

    logger.warning("Could not parse routing decision from: %s", raw[:200])
    return "case_agent"  # safe fallback


async def supervisor_node(state: MessagesState) -> Command:
    # Build conversation summary from state
    conversation_lines = []
    for msg in state["messages"]:
        role = msg.get("role", "user") if isinstance(msg, dict) else "user"
        content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
        if role == "user":
            name = "user"
        else:
            name = msg.get("name", role) if isinstance(msg, dict) else role
        conversation_lines.append(f"{name}: {content[:500]}")

    conversation_summary = "\n".join(conversation_lines[-6:])  # last 6 turns

    messages = [
        {"role": "system", "content": SUPERVISOR_BASE},
        {"role": "user", "content": f"Current conversation:\n{conversation_summary}\n\nWho should act next?"},
    ]

    # Use plain invoke without with_structured_output — the local LLM server
    # doesn't support OpenAI function/tool calling, so we parse JSON from text.
    response = await llm.ainvoke(messages)
    raw_text = response.content if hasattr(response, "content") else str(response)
    next_agent = _parse_next(raw_text)

    goto = END if next_agent == "FINISH" else next_agent
    return Command(goto=goto)


_graph = None


def get_graph():
    """
    Lazily build and cache the compiled supervisor graph. Kept lazy (like
    app/agent.py's get_agent) so tool discovery only happens once, on
    first use, rather than at import time.
    """
    global _graph
    if _graph is None:
        builder = StateGraph(MessagesState)

        builder.add_node("supervisor", supervisor_node)
        builder.add_node("bureau_agent", bureau_node)
        builder.add_node("aml_agent", aml_node)
        builder.add_node("compliance_agent", compliance_node)
        builder.add_node("case_agent", case_node)

        builder.add_edge(START, "supervisor")

        _graph = builder.compile()
    return _graph


async def investigate_fraud_multiagent(data: str):
    """
    True multi-agent entry point. Same signature/return-shape contract as
    app.agent.investigate_fraud (takes a prompt string, returns the final
    graph state dict with a "messages" list), so api.py can use either
    implementation interchangeably.
    """
    graph = get_graph()
    response = await graph.ainvoke({"messages": [("user", data)]})
    return response