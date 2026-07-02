import os

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from app.mcp_client import get_tools

llm = ChatOpenAI(
    model="gpt-5-mini",
   # temperature=0,          # deterministic — this is a fraud/compliance workflow
    api_key=os.getenv("OPENAI_API_KEY"),
)

_agent = None


async def get_agent():
    """
    Lazily build the agent once, using tools discovered live from the
    MCP server. Subsequent calls reuse the same compiled graph.
    """
    global _agent
    if _agent is None:
        tools = await get_tools()
        _agent = create_react_agent(llm, tools)
    return _agent


async def investigate_fraud(data: str):
    agent = await get_agent()
    response = await agent.ainvoke({
        "messages": [
            ("user", data)
        ]
    })
    return response