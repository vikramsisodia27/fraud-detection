"""
fraud-agent-service application package.

Provides a shared ChatOpenAI singleton (OpenAI-compatible) used by the
supervisor and all specialist agents, so they reuse the same connection
pool and token bucket across every LLM call in the investigation flow.

The LLM backend is an OpenAI-compatible endpoint — by default this is a
local vLLM server serving Qwen/Qwen2.5-1.5B-Instruct. To switch
back to OpenAI proper, change LLM_BASE_URL to
"https://api.openai.com/v1" and LLM_MODEL to the model of your choice.
"""

import os
from functools import lru_cache

from langchain.globals import set_llm_cache
from langchain_community.cache import InMemoryCache
from langchain_openai import ChatOpenAI

# Enable in-memory LLM response cache as a safety net.
# This reduces repeated calls with identical inputs (rare in this flow
# due to growing conversation state, but provides a fallback).
set_llm_cache(InMemoryCache())

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://local-llm-service:8001/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
LLM_API_KEY = os.getenv("LLM_API_KEY", "EMPTY")  # vLLM accepts any key; never empty


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