from pydantic import BaseModel


class InvestigationResult(BaseModel):
    fraud_report: str
    aml_report: str
    risk_report: str
    final_decision: str