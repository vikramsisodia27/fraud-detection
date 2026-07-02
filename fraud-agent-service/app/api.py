import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.fraud_client import get_prediction
from app.agent import investigate_fraud

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="fraud-agent-service")

FRAUD_SCORE_THRESHOLD = 0.70


class InvestigateRequest(BaseModel):
    customer_id: str
    transaction_id: str
    features: list


@app.get("/")
def health():
    return {"status": "UP"}


@app.post("/investigate")
async def investigate(request: InvestigateRequest):
    try:
        prediction = get_prediction(request.features)
    except Exception:
        logger.exception("ML API call failed")
        raise HTTPException(status_code=502, detail="Prediction service unavailable")

    fraud_score = prediction.get("fraud_score", 0)

    if fraud_score < FRAUD_SCORE_THRESHOLD:
        return {
            "prediction": prediction,
            "investigation_triggered": False,
        }

    prompt = f"""
    Customer ID: {request.customer_id}
    Transaction ID: {request.transaction_id}
    Prediction: {prediction.get('prediction')}
    Fraud Score: {fraud_score}
    Risk Level: HIGH

    Perform fraud investigation.

    Execute:
    1. bureau_check
    2. aml_check
    3. customer_context
    4. create_case

    Use customer_context to retrieve previous fraud cases, analyst
    comments, investigation notes, SAR reports, emails, and KYC
    documents, and use that information while creating the
    investigation summary.
    """

    try:
        agent_result = await investigate_fraud(prompt)
    except Exception:
        logger.exception("Agent investigation failed")
        raise HTTPException(status_code=500, detail="Investigation failed")

    return {
        "prediction": prediction,
        "investigation_triggered": True,
        "agent_result": agent_result,
    }