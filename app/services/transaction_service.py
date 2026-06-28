from app.services.fraud_ml_service import FraudMLService
from app.services.orchestrator_service import OrchestratorService


class TransactionService:

    def __init__(self):
        self.ml_service = FraudMLService()
        self.orchestrator = OrchestratorService()

    def process_transaction(
            self,
            customer_id,
            features
    ):

        fraud_result = self.ml_service.score_transaction(
            features
        )

        return self.orchestrator.investigate(
            customer_id,
            fraud_result.fraud_score
        )