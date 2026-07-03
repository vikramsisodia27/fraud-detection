"""
Domain-specialist agents for the fraud investigation team.

Each module here is a small, narrowly-scoped agent that only has access to
the one (or few) MCP tool(s) relevant to its job — as opposed to the single
do-everything ReAct agent in app/agent.py, which has all tools at once.

Every specialist exposes a `<name>_node(state) -> Command` function so it
can be dropped straight into the LangGraph StateGraph built in
app/supervisor.py.
"""

from app.agents.bureau_agent import bureau_node
from app.agents.aml_agent import aml_node
from app.agents.compliance_agent import compliance_node
from app.agents.case_agent import case_node

__all__ = [
    "bureau_node",
    "aml_node",
    "compliance_node",
    "case_node",
]