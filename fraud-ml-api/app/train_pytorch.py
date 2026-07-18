"""
PyTorch Neural Net training pipeline for fraud detection.

Replaces (or runs alongside) the existing RandomForest classifier.
Trains a small feed-forward network on fraud_transactions.csv and logs
the trained model to MLflow under "fraud-detector-pytorch".
"""

import argparse
import logging

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report
from torch.utils.data import DataLoader, TensorDataset

import mlflow
import mlflow.pytorch

from config import MLFLOW_TRACKING_URI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------- Reproducibility ---------------
torch.manual_seed(42)
np.random.seed(42)

# --------------- Model Definition ---------------

class FraudNN(nn.Module):
    """Simple feed-forward network for tabular fraud classification."""

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


# --------------- Training ---------------

def train_pytorch(epochs: int = 50, batch_size: int = 32, lr: float = 1e-3):
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    # ---------------------------------------------------
    # Load + preprocess data (same as sklearn train.py)
    # ---------------------------------------------------
    df = pd.read_csv("fraud_transactions.csv")

    categorical_cols = [
        "merchant_category",
        "payment_method",
        "ip_country",
        "customer_country",
    ]
    for col in categorical_cols:
        encoder = LabelEncoder()
        df[col] = encoder.fit_transform(df[col])

    X = df.drop(columns=["is_fraud"]).values.astype(np.float32)
    y = df["is_fraud"].values.astype(np.int64)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # ---------------------------------------------------
    # PyTorch DataLoaders
    # ---------------------------------------------------
    train_dataset = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train))
    test_dataset = TensorDataset(torch.from_numpy(X_test), torch.from_numpy(y_test))

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

    # ---------------------------------------------------
    # Model, Loss, Optimizer
    # ---------------------------------------------------
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = FraudNN(input_dim=X.shape[1], num_classes=2).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)

    logger.info("Training FraudNN on %s — %d samples, %d features",
                device, len(X_train), X.shape[1])

    # ---------------------------------------------------
    # MLflow Tracking
    # ---------------------------------------------------
    with mlflow.start_run() as run:
        mlflow.log_param("model_type", "FraudNN")
        mlflow.log_param("epochs", epochs)
        mlflow.log_param("batch_size", batch_size)
        mlflow.log_param("learning_rate", lr)
        mlflow.log_param("input_dim", X.shape[1])
        mlflow.log_param("architecture", str(model))

        for epoch in range(1, epochs + 1):
            model.train()
            train_loss = 0.0
            for Xb, yb in train_loader:
                Xb, yb = Xb.to(device), yb.to(device)
                optimizer.zero_grad()
                outputs = model(Xb)
                loss = criterion(outputs, yb)
                loss.backward()
                optimizer.step()
                train_loss += loss.item() * Xb.size(0)

            train_loss /= len(train_loader.dataset)

            # Validation every 5 epochs
            if epoch % 5 == 0 or epoch == epochs:
                model.eval()
                val_loss = 0.0
                correct = 0
                total = 0
                with torch.no_grad():
                    for Xb, yb in test_loader:
                        Xb, yb = Xb.to(device), yb.to(device)
                        outputs = model(Xb)
                        loss = criterion(outputs, yb)
                        val_loss += loss.item() * Xb.size(0)
                        _, predicted = torch.max(outputs, 1)
                        total += yb.size(0)
                        correct += (predicted == yb).sum().item()

                val_loss /= len(test_loader.dataset)
                val_acc = correct / total

                mlflow.log_metric("train_loss", train_loss, step=epoch)
                mlflow.log_metric("val_loss", val_loss, step=epoch)
                mlflow.log_metric("val_accuracy", val_acc, step=epoch)

                logger.info(
                    "Epoch %3d/%d — train_loss=%.4f  val_loss=%.4f  val_acc=%.4f",
                    epoch, epochs, train_loss, val_loss, val_acc,
                )

        # ---------------------------------------------------
        # Final evaluation
        # ---------------------------------------------------
        model.eval()
        all_preds = []
        all_labels = []
        with torch.no_grad():
            for Xb, yb in test_loader:
                Xb, yb = Xb.to(device), yb.to(device)
                outputs = model(Xb)
                _, predicted = torch.max(outputs, 1)
                all_preds.extend(predicted.cpu().numpy())
                all_labels.extend(yb.cpu().numpy())

        accuracy = np.mean(np.array(all_preds) == np.array(all_labels))
        report = classification_report(all_labels, all_preds)

        mlflow.log_metric("accuracy", accuracy)
        logger.info("\n" + report)
        logger.info("Accuracy = %.4f", accuracy)

        # ---------------------------------------------------
        # Log model to MLflow
        # ---------------------------------------------------
        # Create a sample input for the signature
        sample_input = torch.from_numpy(X_test[:1])
        mlflow.pytorch.log_model(
            pytorch_model=model,
            artifact_path="model",
            registered_model_name="fraud-detector-pytorch",
        )

        logger.info("Model logged to MLflow as 'fraud-detector-pytorch'")

    return {"run_id": run.info.run_id, "accuracy": accuracy}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    args = parser.parse_args()
    train_pytorch(epochs=args.epochs, batch_size=args.batch_size, lr=args.lr)