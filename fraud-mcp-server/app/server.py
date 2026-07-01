from fastapi import FastAPI
from app.vector.rag_service import RagService

app = FastAPI()


@app.get("/")
def health():
    return {
        "status": "UP"
    }


@app.get("/bureau_check/{customer_id}")
def bureau_check(customer_id: str):

    # Replace with actual bureau service/database
    return {
        "customer_id": customer_id,
        "bureau_score": 740,
        "delinquencies": 0
    }


@app.get("/aml_check/{customer_id}")
def aml_check(customer_id: str):

    # Replace with actual AML system
    return {
        "customer_id": customer_id,
        "status": "CLEAR"
    }


@app.post("/create_case")
def create_case(payload: dict):

    # Replace with Case Management System

    return {
        "case_id": "CASE-1001",
        "status": "CREATED",
        "payload": payload
    }


@app.get("/customer_context/{customer_id}")
def customer_context(customer_id: str):

    context = RagService.build_customer_context(customer_id)

    return {
        "customer_id": customer_id,
        "context": context
    }