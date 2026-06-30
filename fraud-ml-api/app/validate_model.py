import mlflow
from config import MLFLOW_TRACKING_URI
THRESHOLD = 0.90


def validate():


    mlflow.set_tracking_uri(
        MLFLOW_TRACKING_URI
    )

    client = mlflow.tracking.MlflowClient()

    versions = client.search_model_versions(
        "name='fraud-detector'"
    )

    latest = max(
        versions,
        key=lambda x: int(x.version)
    )

    run = client.get_run(
        latest.run_id
    )

    accuracy = float(
        run.data.metrics["accuracy"]
    )

    print(
        f"Model Accuracy = {accuracy}"
    )

    if accuracy >= THRESHOLD:
        print("Validation Passed")

        return {
            "accuracy": accuracy
        }

    raise Exception(
        "Validation Failed"
    )


if __name__ == "__main__":
    validate()