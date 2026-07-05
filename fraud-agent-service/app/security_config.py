import os

REALM = os.getenv("KEYCLOAK_REALM", "fraud_detection_realm")
AUTH_SERVER_URL = os.getenv("KEYCLOAK_BASE_URL", "http://keycloak:8080")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "fraud-agent-service")
CLIENT_SECRET = os.getenv("FRAUD_AGENT_CLIENT_SECRET","AhP7HCxMGJ5NhHjCbxi8jopfJGrIXlT1")

TOKEN_URL = f"{AUTH_SERVER_URL}/realms/{REALM}/protocol/openid-connect/token"

# path -> Keycloak resource name. Add new protected routes here only —
# no code changes needed elsewhere when you protect a new endpoint.
PATH_TO_RESOURCE = {
    "/investigate": "investigate-resource",
    # "/cases": "case-resource",   # example for later
}