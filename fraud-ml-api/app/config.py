import os

# Cross-namespace DNS: mlflow lives in the "mlflow-infra" namespace
# Same-namespace fallback "http://mlflow:5000" won't work anymore.
MLFLOW_TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    "http://mlflow.mlflow-infra.svc.cluster.local:5000"
)
