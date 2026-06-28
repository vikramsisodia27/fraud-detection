class ApprovalService:

    def requires_manual_review(
            self,
            fraud_score: float
    ) -> bool:

        return fraud_score >= 0.85