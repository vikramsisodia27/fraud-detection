import time
import asyncio
import httpx

from app.security_config import TOKEN_URL, CLIENT_ID, CLIENT_SECRET

_token_cache = {"token": None, "expires_at": 0}
_lock = asyncio.Lock()


async def get_service_token() -> str:
    """Fetch and cache this service's own client-credentials token.
    Refreshes ~30s before expiry. Safe for concurrent callers."""
    now = time.time()

    if _token_cache["token"] and now < (_token_cache["expires_at"] - 30):
        return _token_cache["token"]

    async with _lock:
        now = time.time()
        if _token_cache["token"] and now < (_token_cache["expires_at"] - 30):
            return _token_cache["token"]

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "grant_type": "client_credentials",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = now + data["expires_in"]
        return _token_cache["token"]