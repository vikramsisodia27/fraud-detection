from fastapi import FastAPI

from app.fraud_client import get_prediction
from app.agent import investigate_fraud

app = FastAPI()

@app.post("/investigate")
def investigate(payload: dict):

    features = payload["features"]

    prediction = get_prediction(features)

    result = investigate_fraud(
        f"Fraud score = {prediction['fraud_score']}"
    )

    return {
        "prediction": prediction,
        "agent_result": str(result)
    }
