"""
fraud-agent-service application package.

Provides a shared ChatOpenAI singleton (OpenAI-compatible) used by the
supervisor and all specialist agents, so they reuse the same connection
pool and token bucket across every LLM call in the investigation flow.

The LLM backend is an OpenAI-compatible endpoint. By default this uses
OpenAI proper (https://api.openai.com/v1). To switch to a local LLM,
change LLM_BASE_URL to "http://<service>:<port>/v1" and LLM_MODEL
to the model name of your choice.
"""

import os
from functools import lru_cache

from langchain.globals import set_llm_cache
from langchain_community.cache import InMemoryCache
from langchain_openai import ChatOpenAI

# Enable in-memory LLM response cache as a safety net.
set_llm_cache(InMemoryCache())

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """
    Return the single shared LLM instance.

    Cached via lru_cache so every call returns the exact same object
    (identity check passes). This ensures the supervisor and all
    specialist agents share connection pooling and consistent backend
    configuration.
    """
    return ChatOpenAI(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        # temperature=0 — deterministic fraud/compliance workflow
        temperature=0,
    )