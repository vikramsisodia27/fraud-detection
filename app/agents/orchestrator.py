from typing import TypedDict
from langgraph.graph import StateGraph
from langgraph.graph import END

from app.agents.fraud_agent import fraud_agent
from app.agents.aml_agent import aml_agent
from app.agents.risk_agent import risk_agent
from app.agents.decision_agent import decision_agent


class FraudState(TypedDict):
    customer_id: str
    fraud_score: float
    fraud_report: str
    aml_report: str
    risk_report: str
    decision: str


def fraud_node(state):

    result = fraud_agent.invoke({
        "messages": [
            (
                "user",
                f"""
                Investigate customer
                {state['customer_id']}
                with fraud score
                {state['fraud_score']}
                """
            )
        ]
    })

    state["fraud_report"] = str(result)
    return state


def aml_node(state):

    result = aml_agent.invoke({
        "messages": [
            (
                "user",
                f"""
                Perform AML investigation
                for customer
                {state['customer_id']}
                """
            )
        ]
    })

    state["aml_report"] = str(result)
    return state


def risk_node(state):

    result = risk_agent.invoke({
        "messages": [
            (
                "user",
                f"""
                Determine customer risk
                for customer
                {state['customer_id']}
                """
            )
        ]
    })

    state["risk_report"] = str(result)
    return state


def decision_node(state):

    result = decision_agent.invoke({
        "messages": [
            (
                "user",
                f"""
                Fraud Report:
                {state['fraud_report']}

                AML Report:
                {state['aml_report']}

                Risk Report:
                {state['risk_report']}

                Produce final recommendation.
                Create case only if required.
                """
            )
        ]
    })

    state["decision"] = str(result)
    return state


builder = StateGraph(FraudState)

builder.add_node("fraud", fraud_node)
builder.add_node("aml", aml_node)
builder.add_node("risk", risk_node)
builder.add_node("decision", decision_node)

builder.set_entry_point("fraud")

builder.add_edge("fraud", "aml")
builder.add_edge("aml", "risk")
builder.add_edge("risk", "decision")
builder.add_edge("decision", END)

fraud_workflow = builder.compile()