import bentoml
import mlflow
import numpy as np
import logging

import torch
import torch.nn as nn

from app.llm_scorer import score_text

logger = logging.getLogger(__name__)

RF_WEIGHT = 0.7
BERT_WEIGHT = 0.3

# --------------- PyTorch model definition (must match train_pytorch.py) ---------------

class FraudNN(nn.Module):
    """Must match the architecture in train_pytorch.py."""

    def __init__(self, input_dim: int = 10, num_classes: int = 2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, num_classes),
        )

    def forward(self, x):
        return self.net(x)


# --------------- Service ---------------

@bentoml.service
class FraudDetectionService:

    def __init__(self):
        self.model = None
        self.model_type = None  # "sklearn" or "pytorch"

    def load_model(self):
        if self.model is not None:
            return

        # Try PyTorch model first, fall back to sklearn
        try:
            logger.info("Attempting to load PyTorch model 'fraud-detector-pytorch:latest'")
            self.model = mlflow.pytorch.load_model("models:/fraud-detector-pytorch/latest")
            self.model.eval()
            self.model_type = "pytorch"
            logger.info("Loaded PyTorch model")
            return
        except Exception:
            logger.info("PyTorch model not found — falling back to sklearn RandomForest")

        # Fallback: sklearn model (original)
        try:
            self.model = bentoml.mlflow.load_model("fraud-detector:latest")
            self.model_type = "sklearn"
            logger.info(f"Loaded sklearn model type: {type(self.model)}")
        except Exception:
            logger.exception("Failed to load sklearn model")
            raise

    def _predict_sklearn(self, features: np.ndarray) -> tuple:
        """Run sklearn model, return (prediction_class, fraud_score)."""
        prediction = self.model.predict(features)
        pred_class = int(prediction[0])

        fraud_score = None
        try:
            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba(features)
                fraud_score = float(proba[0][1])
        except Exception:
            logger.exception("predict_proba failed")

        if fraud_score is None:
            fraud_score = 0.90 if pred_class == 1 else 0.10

        return pred_class, fraud_score

    def _predict_pytorch(self, features: np.ndarray) -> tuple:
        """Run PyTorch model, return (prediction_class, fraud_score)."""
        device = next(self.model.parameters()).device
        tensor = torch.from_numpy(features).float().to(device)

        with torch.no_grad():
            outputs = self.model(tensor)
            probabilities = torch.softmax(outputs, dim=1)
            pred_class = int(torch.argmax(probabilities, dim=1).item())
            fraud_score = float(probabilities[0, 1].item())

        return pred_class, fraud_score

    @bentoml.api
    async def predict(self, input_data: dict):

        self.load_model()

        features = np.array([input_data["features"]])

        if self.model_type == "pytorch":
            pred_class, rf_score = self._predict_pytorch(features)
        else:
            pred_class, rf_score = self._predict_sklearn(features)

        response = {"prediction": pred_class}

        # ---------------------------------------------------------------
        # Ensemble: blend RF/NN score with BERT text sentiment score
        # ---------------------------------------------------------------
        text = input_data.get("text", "")
        bert_score = None

        if text:
            try:
                bert_score = await score_text(text)
            except Exception:
                logger.exception("BERT scoring failed in predict")

        if bert_score is not None:
            fraud_score = RF_WEIGHT * rf_score + BERT_WEIGHT * bert_score
            logger.info(
                "Ensemble score (%s): rf=%.4f bert=%.4f final=%.4f",
                self.model_type, rf_score, bert_score, fraud_score,
            )
        else:
            fraud_score = rf_score
            logger.info(
                "%s-only score: %.4f (no BERT input or BERT failed)",
                self.model_type, fraud_score,
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