from langgraph.prebuilt import create_react_agent
from app.agents.llm import llm
from app.tools.decision_tools import DECISION_TOOLS

decision_agent = create_react_agent(
    llm,
    DECISION_TOOLS
)