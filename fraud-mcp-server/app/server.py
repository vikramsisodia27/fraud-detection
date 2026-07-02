"""
fraud-mcp-server — a *true* MCP server.

Replaces the earlier FastAPI-with-plain-REST-routes implementation.
Tools are registered with the MCP SDK (FastMCP), giving us:
  - typed tool schemas (auto-generated from function signatures / docstrings)
  - standard MCP transport (Streamable HTTP here; stdio also works for local dev)
  - tool discovery: any MCP-compatible client (LangGraph, Claude Desktop,
    LangChain's MultiServerMCPClient, etc.) can list + call these tools
    without bespoke REST-client glue code.

Run:
    python -m app.server   → starts streamable-http on 0.0.0.0:9000/mcp
"""

import logging
from pydantic import BaseModel, Field

from mcp.server.fastmcp import FastMCP

from app.vector.rag_service import RagService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="fraud-investigation-mcp-server",
    host="0.0.0.0",
    port=9000,
    stateless_http=True,   # each call is independent — fine for our use case
)


# ---------------------------------------------------------------------------
# Structured output schemas (typed, not free-text JSON blobs)
# ---------------------------------------------------------------------------

class BureauCheckResult(BaseModel):
    customer_id: str
    bureau_score: int
    delinquencies: int


class AmlCheckResult(BaseModel):
    customer_id: str
    status: str


class CustomerContextResult(BaseModel):
    customer_id: str
    context: str
    document_count: int


class CreateCasePayload(BaseModel):
    case_title: str = Field(..., description="Short human-readable case title")
    customer_id: str
    transaction_id: str
    prediction: int
    fraud_score: float
    risk_level: str
    investigation_summary: str
    recommended_actions: list[str] = Field(default_factory=list)
    priority: str = "MEDIUM"


class CreateCaseResult(BaseModel):
    case_id: str
    status: str


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def bureau_check(customer_id: str) -> BureauCheckResult:
    """
    Perform a credit bureau check for a customer.

    NOTE: Currently a stub. Replace with a real bureau vendor
    integration (e.g. Experian/Equifax/CIBIL API call).
    """
    return BureauCheckResult(
        customer_id=customer_id,
        bureau_score=740,
        delinquencies=0,
    )


@mcp.tool()
def aml_check(customer_id: str) -> AmlCheckResult:
    """
    Perform an AML (Anti-Money-Laundering) screening check for a customer.

    NOTE: Currently a stub. Replace with a real AML/sanctions
    screening vendor integration.
    """
    return AmlCheckResult(
        customer_id=customer_id,
        status="CLEAR",
    )


@mcp.tool()
def customer_context(customer_id: str, limit: int = 5) -> CustomerContextResult:
    """
    Retrieve historical customer context via RAG over the vector store.

    Returns previous fraud cases, investigation notes, analyst comments,
    SAR reports, emails, and KYC documents relevant to this customer.
    """
    documents = RagService.retrieve_customer_context(customer_id, limit)
    context_text = RagService.format_documents(documents, customer_id)

    return CustomerContextResult(
        customer_id=customer_id,
        context=context_text,
        document_count=len(documents),
    )


@mcp.tool()
def create_case(payload: CreateCasePayload) -> CreateCaseResult:
    """
    Create a fraud investigation case in the case management system.

    NOTE: Currently a stub returning a fixed case ID. Replace with a
    real case-management-system integration (Jira Service Mgmt,
    ServiceNow, an internal CMS, etc.) that returns a real generated ID.
    """
    logger.info("Creating case for customer_id=%s transaction_id=%s",
                payload.customer_id, payload.transaction_id)

    return CreateCaseResult(
        case_id=f"CASE-{payload.transaction_id}",
        status="CREATED",
    )


@mcp.tool()
def health() -> dict:
    """Health check."""
    return {"status": "UP"}


if __name__ == "__main__":
    # streamable-http exposes the server at /mcp on the given port
    mcp.run(transport="streamable-http")