from pydantic import BaseModel


class FraudResult(BaseModel):
    prediction: int
    fraud_score: float