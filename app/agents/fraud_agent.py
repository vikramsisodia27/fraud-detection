from langgraph.prebuilt import create_react_agent
from app.agents.llm import llm
from app.tools.fraud_tools import FRAUD_TOOLS

fraud_agent = create_react_agent(
    llm,
    FRAUD_TOOLS
)