"""
# COMMENTED OUT: FinBERT/SLM Fraud Scorer (not currently in use)
#
# This module used ProsusAI/finbert as a secondary fraud signal
# in the ensemble. It is retained for future reference.

import asyncio
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 2.0

@lru_cache(maxsize=1)
def _get_pipeline():
    from transformers import pipeline
    logger.info("Loading FinBERT pipeline (first call — cached thereafter)")
    return pipeline("text-classification", model="ProsusAI/finbert", top_k=None)

def _score_sync(text: str) -> float | None:
    try:
        pipe = _get_pipeline()
        result = pipe(text, truncation=True, max_length=512)
        scores = {item["label"]: item["score"] for item in result[0]}
        fraud_prob = scores.get("negative", 0.0)
        return fraud_prob
    except Exception:
        return None

async def score_text(text: str) -> float | None:
    loop = asyncio.get_running_loop()
    try:
        fraud_prob = await asyncio.wait_for(
            loop.run_in_executor(None, _score_sync, text),
            timeout=TIMEOUT_SECONDS,
        )
        return fraud_prob
    except asyncio.TimeoutError:
        return None
    except Exception:
        return None
"""