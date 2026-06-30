import mlflow
import bentoml
from config import MLFLOW_TRACKING_URI

def import_model():


    mlflow.set_tracking_uri(
        MLFLOW_TRACKING_URI
    )

    model_uri = (
        "models:/fraud-detector/Production"
    )

    bentoml.mlflow.import_model(
        name="fraud-detector",
        model_uri=model_uri
    )

    print(
        "Model imported successfully."
    )


if __name__ == "__main__":
    import_model()