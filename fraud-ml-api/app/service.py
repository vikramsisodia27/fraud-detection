import bentoml
import numpy as np
import logging

logger = logging.getLogger(__name__)


@bentoml.service
class FraudDetectionService:

    def __init__(self):
        self.model = None

    def load_model(self):
        if self.model is None:
            self.model = bentoml.mlflow.load_model(
                "fraud-detector:latest"
            )
            logger.info(
                f"Loaded model type: {type(self.model)}"
            )

    @bentoml.api
    def predict(self, input_data: dict):

        self.load_model()

        features = np.array(
            [input_data["features"]]
        )

        prediction = self.model.predict(features)

        response = {
            "prediction": int(prediction[0])
        }

        fraud_score = None

        try:
            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba(features)
                fraud_score = float(proba[0][1])

        except Exception:
            logger.exception(
                "predict_proba failed"
            )

        #
        # Fallback when model does not expose
        # predict_proba (PyFuncModel case)
        #
        if fraud_score is None:
            fraud_score = (
                0.90
                if int(prediction[0]) == 1
                else 0.10
            )

        response["fraud_score"] = fraud_score

        if fraud_score >= 0.80:
            risk_level = "HIGH"
        elif fraud_score >= 0.50:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        response["risk_level"] = risk_level

        return response