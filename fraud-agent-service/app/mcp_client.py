import requests
from langchain_core.tools import tool

MCP_SERVER = "http://fraud-mcp-server:9000"


@tool
def bureau_check(customer_id: str):
    """Perform bureau check for a customer."""

    response = requests.get(
        f"{MCP_SERVER}/bureau_check/{customer_id}"
    )
    return response.json()


@tool
def aml_check(customer_id: str):
    """Perform AML check for a customer."""

    response = requests.get(
        f"{MCP_SERVER}/aml_check/{customer_id}"
    )
    return response.json()


@tool
def create_case(payload: str):
    """Create a fraud investigation case."""

    response = requests.post(
        f"{MCP_SERVER}/create_case",
        json={"payload": payload}
    )
    return response.json()


TOOLS = [
    bureau_check,
    aml_check,
    create_case
]