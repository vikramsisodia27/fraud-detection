from fastapi import FastAPI

app = FastAPI()

TOOLS = [
    {
        "name": "bureau_check",
        "description": "Get bureau score"
    },
    {
        "name": "aml_check",
        "description": "AML verification"
    },
    {
        "name": "create_case",
        "description": "Create fraud case"
    }
]

@app.get("/tools")
def tools():
    return TOOLS

@app.get("/bureau_check/{customer_id}")
def bureau_check(customer_id: str):

    return {
        "customer_id": customer_id,
        "bureau_score": 740
    }

@app.get("/aml_check/{customer_id}")
def aml_check(customer_id: str):

    return {
        "customer_id": customer_id,
        "status": "CLEAR"
    }

@app.post("/create_case")
def create_case(payload: dict):

    return {
        "case_id": "CASE-1001",
        "status": "CREATED"
    }
