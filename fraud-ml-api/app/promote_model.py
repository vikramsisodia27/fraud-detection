import mlflow
from config import MLFLOW_TRACKING_URI

def promote():


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

    client.transition_model_version_stage(
        name="fraud-detector",
        version=latest.version,
        stage="Production"
    )

    print(
        f"Version {latest.version} promoted to Production"
    )

    return latest.version


if __name__ == "__main__":
    promote()