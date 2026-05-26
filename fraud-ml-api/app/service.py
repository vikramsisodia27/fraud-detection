import bentoml
import numpy as np

@bentoml.service
class FraudDetectionService:

    def __init__(self):
        self.model = bentoml.mlflow.load_model("fraud-detector:latest")

    @bentoml.api
    def predict(self, input_data: dict):

        features = np.array([input_data["features"]])

        # FIX: MLflow model call
        prediction = self.model.predict(features)

        try:
            proba = self.model.predict_proba(features)
            return {
                "prediction": int(prediction[0]),
                "fraud_score": float(proba[0][1])
            }
        except Exception:
            return {
                "prediction": int(prediction[0])
            }