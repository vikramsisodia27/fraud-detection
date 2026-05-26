import requests

FRAUD_API = "http://fraud-ml-api:3000"

def get_prediction(features):

    response = requests.post(
        f"{FRAUD_API}/predict",
        json={"features": features}
    )

    return response.json()
