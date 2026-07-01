import os
import requests

ML_API_URL = os.getenv(
    "ML_API_URL",
    "http://fraud-ml-api:3000"
)


def get_prediction(features):

    response = requests.post(
        f"{ML_API_URL}/predict",
        json={
            "input_data": {
                "features": features
            }
        },
        timeout=30
    )

    print("Status:", response.status_code)
    print("Body:", response.text)

    response.raise_for_status()

    return response.json()