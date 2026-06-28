import requests
from app.models.fraud_result import FraudResult

FRAUD_API = "http://localhost:3000"


class FraudMLService:

    def score_transaction(self, features):

        response = requests.post(
            f"{FRAUD_API}/predict",
            json={
                "input_data": {
                    "features": features
                }
            }
        )

        response.raise_for_status()

        data = response.json()

        return FraudResult(
            prediction=data["prediction"],
            fraud_score=data["fraud_score"]
        )