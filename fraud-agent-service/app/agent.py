from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from app.mcp_client import TOOLS

llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    temperature=0
)

agent = create_react_agent(
    llm,
    TOOLS
)

def investigate_fraud(data: str):

    response = agent.invoke({
        "messages": [
            ("user", data)
        ]
    })

    return response
