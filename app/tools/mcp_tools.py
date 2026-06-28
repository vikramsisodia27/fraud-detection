import requests
from langchain_core.tools import tool

MCP_SERVER = "http://localhost:9000"


@tool
def bureau_check(customer_id: str):
    """Get customer bureau details."""
    return requests.get(
        f"{MCP_SERVER}/bureau_check/{customer_id}"
    ).json()


@tool
def aml_check(customer_id: str):
    """Perform AML checks."""
    return requests.get(
        f"{MCP_SERVER}/aml_check/{customer_id}"
    ).json()


@tool
def create_case(payload: str):
    """Create fraud investigation case."""
    return requests.post(
        f"{MCP_SERVER}/create_case",
        json={"payload": payload}
    ).json()