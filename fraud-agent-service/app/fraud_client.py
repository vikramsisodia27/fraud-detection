import os

import httpx

from app.token_manager import get_service_token

ML_API_URL = os.getenv(
    "ML_API_URL",
    "http://fraud-ml-api:3000"
)


async def get_prediction(features):
    token = await get_service_token()

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{ML_API_URL}/predict",
            json={
                "input_data": {
                    "features": features
                }
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        response.raise_for_status()
        return response.json()