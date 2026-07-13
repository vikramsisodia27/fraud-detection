"""
fraud-agent-service application package.

Provides a shared ChatOpenAI singleton used by the supervisor and all
specialist agents, so they reuse the same connection pool, token bucket,
and prompt-cache prefix across every LLM call in the investigation flow.
"""

import os
from functools import lru_cache

from langchain.globals import set_llm_cache
from langchain.cache import InMemoryCache
from langchain_openai import ChatOpenAI

# Enable in-memory LLM response cache as a safety net.
# This reduces repeated calls with identical inputs (rare in this flow
# due to growing conversation state, but provides a fallback).
set_llm_cache(InMemoryCache())


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """
    Return the single shared LLM instance.

    Cached via lru_cache so every call returns the exact same object
    (identity check passes). This ensures the supervisor and all
    specialist agents share connection pooling and OpenAI's server-side
    prompt cache prefix.
    """
    return ChatOpenAI(
        model="gpt-5-mini",
        # temperature=0 — deterministic fraud/compliance workflow
        api_key=os.getenv("OPENAI_API_KEY"),
    )