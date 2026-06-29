import mlflow
import bentoml

mlflow.set_tracking_uri("http://localhost:5001")

model_uri = "models:/fraud-detector/Production"

bentoml.mlflow.import_model(
    name="fraud-detector",
    model_uri=model_uri
)

print("Model imported successfully.")