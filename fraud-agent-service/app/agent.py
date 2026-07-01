#from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
import os

from app.mcp_client import TOOLS

llm = ChatOpenAI(
    #model="claude-3-5-sonnet-20241022",
    model="gpt-5-mini",
    temperature=1,
    api_key=os.getenv("OPENAI_API_KEY")
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


