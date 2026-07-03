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

import os
from typing import TypedDict, Literal

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.types import Command

from app.agents import bureau_node, aml_node, compliance_node, case_node

MEMBERS = ["bureau_agent", "aml_agent", "compliance_agent", "case_agent"]
OPTIONS = MEMBERS + ["FINISH"]

SUPERVISOR_PROMPT = f"""You are the supervisor of a fraud-investigation team.
You do not call any tools yourself — you only decide, at each step, which
specialist should act next:

- bureau_agent: runs a credit bureau / delinquency check
- aml_agent: runs an AML / sanctions screening check
- compliance_agent: retrieves historical customer context (past fraud
  cases, SAR reports, KYC documents, analyst notes) via RAG
- case_agent: creates the final investigation case record; must run LAST,
  only after bureau_agent, aml_agent, and compliance_agent have all
  reported results in the conversation

Look at the conversation so far and pick exactly one next step from:
{", ".join(OPTIONS)}.

Do not route to case_agent until the other three specialists have each
reported a result. Once case_agent has reported a created case, respond
with FINISH."""


class Router(TypedDict):
    """Structured routing decision."""
    next: Literal["bureau_agent", "aml_agent", "compliance_agent", "case_agent", "FINISH"]


llm = ChatOpenAI(
    model="gpt-5-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
)


async def supervisor_node(state: MessagesState) -> Command:
    messages = [{"role": "system", "content": SUPERVISOR_PROMPT}] + state["messages"]
    router = llm.with_structured_output(Router)
    decision = await router.ainvoke(messages)

    goto = decision["next"]
    if goto == "FINISH":
        goto = END

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