from pydantic import BaseModel


class Transaction(BaseModel):
    customer_id: str
    transaction_id: str
    amount: float
    merchant_category: str
    payment_method: str
    customer_country: str