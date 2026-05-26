import bentoml

bentoml.mlflow.import_model(
    "fraud-detector",
    model_uri="models:/fraud-detector/Production"
)

print("Imported into BentoML")
