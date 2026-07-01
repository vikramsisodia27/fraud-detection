from fastapi import FastAPI, HTTPException

from app.fraud_client import get_prediction
from app.agent import investigate_fraud

app = FastAPI()


@app.post("/investigate")
def investigate(payload: dict):

    try:
        features = payload["features"]

        customer_id = payload.get(
            "customer_id",
            "UNKNOWN"
        )

        transaction_id = payload.get(
            "transaction_id",
            "UNKNOWN"
        )

        prediction = get_prediction(features)

        fraud_score = prediction["fraud_score"]

        if fraud_score < 0.70:
            return {
                "prediction": prediction,
                "message":
                    "No investigation required"
            }

        prompt = f"""
        Customer ID: {customer_id}
        Transaction ID: {transaction_id}
        Prediction: {prediction['prediction']}
        Fraud Score: {fraud_score}
        Risk Level: {prediction['risk_level']}

        Perform fraud investigation.

        Execute:
        1. bureau_check
        2. aml_check
        3. create_case

        Return investigation summary.
        """

        result = investigate_fraud(prompt)

        return {
            "prediction": prediction,
            "agent_result": str(result)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )