"""
SLM (Small Language Model) Fraud Scorer.

Uses ProsusAI/finbert — a financial-domain BERT model (110M params) —
as a secondary fraud signal in the ensemble. Runs CPU-only with a
2-second timeout. Singleton pattern so the model is loaded once per
process and reused across all requests.

Graceful degradation: any failure (timeout, OOM, model load error)
returns None, and the caller (service.py) falls back to the RF-only
score.
"""

import asyncio
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 2.0


@lru_cache(maxsize=1)
def _get_pipeline():
    """
    Singleton — load the FinBERT pipeline exactly once.

    Cached via lru_cache so every call returns the exact same object
    (identity check passes). This avoids re-loading the 110M-param
    model on every request.
    """
    from transformers import pipeline
    logger.info("Loading FinBERT pipeline (first call — cached thereafter)")
    return pipeline(
        "text-classification",
        model="ProsusAI/finbert",
        # Return all scores so we can extract the "positive" class
        # probability as a proxy for fraud risk
        top_k=None,
    )


def _score_sync(text: str) -> float | None:
    """Synchronous BERT inference. Runs in a thread pool."""
    try:
        pipe = _get_pipeline()
        result = pipe(text, truncation=True, max_length=512)
        # FinBERT returns [{"label": "positive", "score": 0.xx},
        #                  {"label": "negative", "score": 0.xx},
        #                  {"label": "neutral",  score": 0.xx}]
        # We use the "negative" score as a fraud proxy (negative financial
        # sentiment correlates with fraudulent activity in transaction data).
        scores = {item["label"]: item["score"] for item in result[0]}
        # fraud probability: "negative" sentiment score from FinBERT
        fraud_prob = scores.get("negative", 0.0)
        logger.debug("FinBERT scored input: negative=%.4f", fraud_prob)
        return fraud_prob
    except Exception:
        logger.exception("FinBERT scoring failed")
        return None


async def score_text(text: str) -> float | None:
    """
    Score a text string for fraud risk using FinBERT.

    Returns a float 0.0–1.0, or None if the model fails / times out.

    Runs the blocking HuggingFace pipeline in a thread pool executor
    so it doesn't block BentoML's asyncio event loop.
    """
    loop = asyncio.get_running_loop()
    try:
        fraud_prob = await asyncio.wait_for(
            loop.run_in_executor(None, _score_sync, text),
            timeout=TIMEOUT_SECONDS,
        )
        return fraud_prob
    except asyncio.TimeoutError:
        logger.warning("FinBERT scoring timed out after %ss", TIMEOUT_SECONDS)
        return None
    except Exception:
        logger.exception("Unexpected error in FinBERT scoring")
        return None