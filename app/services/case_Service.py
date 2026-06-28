from app.tools.mcp_tools import create_case


class CaseService:

    def create(
            self,
            payload: str
    ):
        return create_case.invoke(
            {"payload": payload}
        )