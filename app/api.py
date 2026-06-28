from fastapi import FastAPI
from app.services.transaction_service import TransactionService

app = FastAPI()

service = TransactionService()


@app.post("/investigate")
def investigate(payload: dict):

    return service.process_transaction(
        payload["customer_id"],
        payload["features"]
    )