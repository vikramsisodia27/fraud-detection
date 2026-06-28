from langgraph.prebuilt import create_react_agent
from app.agents.llm import llm
from app.tools.aml_tools import AML_TOOLS

aml_agent = create_react_agent(
    llm,
    AML_TOOLS
)