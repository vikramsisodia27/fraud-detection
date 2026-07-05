import logging
import httpx
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.security_config import PATH_TO_RESOURCE, TOKEN_URL, CLIENT_ID, CLIENT_SECRET


logger = logging.getLogger("policy_enforcer")


class PolicyEnforcerMiddleware(BaseHTTPMiddleware):
    """
    Central authorization enforcement, equivalent to Keycloak's
    ServletPolicyEnforcerFilter. Every request to a mapped path is
    validated + authorized against Keycloak before reaching the route.
    No per-route auth code needed.
    """

    async def dispatch(self, request: Request, call_next):
        resource = PATH_TO_RESOURCE.get(request.url.path)

        logger.info(f"resource: {resource}")

        if resource is None:
            # not a protected path — pass through
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        logger.info(f"auth_header: {auth_header}")

        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing bearer token"})

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    TOKEN_URL,
                    data={
                        "grant_type": "urn:ietf:params:oauth:grant-type:uma-ticket",
                        "audience": CLIENT_ID,
                        "permission": "investigate-resource",
                        "client_id": CLIENT_ID,
                        "client_secret": CLIENT_SECRET,
                    },
                    headers={
                        "Authorization": auth_header  # Forward the incoming Bearer token
                    },
                )


        except httpx.RequestError as e:
            logger.error(f"Keycloak unreachable during authorization check: {e}")
            # fail closed — do not let requests through if Keycloak is down
            return JSONResponse(status_code=503, content={"detail": "Authorization service unavailable"})

        if resp.status_code == 200:
            return await call_next(request)

        if resp.status_code in (401, 403):
            logger.warning(f"Access denied for {request.url.path}: {resp.text}")
            return JSONResponse(status_code=403, content={"detail": "Access denied"})

        logger.error(f"Unexpected response from Keycloak: {resp.status_code} {resp.text}")
        return JSONResponse(status_code=503, content={"detail": "Authorization check failed"})