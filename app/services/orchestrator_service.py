from app.workflows.fraud_workflow import fraud_workflow


class OrchestratorService:

    def investigate(
            self,
            customer_id: str,
            fraud_score: float
    ):

        state = {
            "customer_id": customer_id,
            "fraud_score": fraud_score,
            "fraud_report": "",
            "aml_report": "",
            "risk_report": "",
            "decision": ""
        }

        return fraud_workflow.invoke(state)