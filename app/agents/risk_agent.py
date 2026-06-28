from langgraph.prebuilt import create_react_agent
from app.agents.llm import llm
from app.tools.risk_tools import RISK_TOOLS

risk_agent = create_react_agent(
    llm,
    RISK_TOOLS
)