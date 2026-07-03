"""
AML (Anti-Money-Laundering) Specialist.

Scoped to the `aml_check` MCP tool only. Owns sanctions / AML screening
and nothing else.
"""

from app.agents._base import make_specialist

SYSTEM_PROMPT = """You are the AML Specialist on a fraud investigation team.

Your only responsibility is to run an AML / sanctions screening check via
the `aml_check` tool for the customer under investigation, then report the
screening status back to the team in 1-2 sentences (CLEAR vs. a flagged
status, and what that implies).

Do not attempt bureau checks, historical case lookups, or case creation —
those belong to other specialists on the team. Once you have called
aml_check and summarized the result, stop."""

get_aml_agent, aml_node = make_specialist(
    agent_name="aml_agent",
    tool_names=["aml_check"],
    system_prompt=SYSTEM_PROMPT,
)