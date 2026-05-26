import mlflow

client = mlflow.tracking.MlflowClient()

client.transition_model_version_stage(
    name="fraud-detector",
    version=1,
    stage="Production"
)

print("Model promoted")
