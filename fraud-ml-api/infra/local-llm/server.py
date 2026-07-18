"""
OpenAI-compatible chat completions API server.

Replaces vLLM for CPU-only environments. Serves Qwen/Qwen2.5-1.5B-Instruct
(or any HuggingFace causal LM) with the same /v1/chat/completions endpoint
that LangChain's ChatOpenAI expects.

Usage:  uvicorn server:app --host 0.0.0.0 --port 8001
"""

import asyncio
import os
import logging
import time
from functools import lru_cache

import torch
from fastapi import FastAPI, Request
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="local-llm-server")

MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-0.5B-Instruct")


# ---------------------------------------------------------------------------
# Singleton model + tokenizer (loaded once, cached forever)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_model_and_tokenizer():
    logger.info("Loading model %s (first call — cached thereafter)", MODEL_NAME)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float32,
        device_map="cpu",
        trust_remote_code=True,
    )
    model.eval()
    logger.info("Model loaded successfully")
    return model, tokenizer


# ---------------------------------------------------------------------------
# Request / Response schemas (OpenAI-compatible subset)
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = MODEL_NAME
    messages: list[ChatMessage]
    temperature: float = 0.0
    max_tokens: int = 1024
    top_p: float = 1.0
    stream: bool = False


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list
    usage: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "UP"}


@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [
            {"id": MODEL_NAME, "object": "model", "created": int(time.time()), "owned_by": "local"}
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    model, tokenizer = _get_model_and_tokenizer()

    # Build the chat template
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # Apply the model's chat template (handles system/user/assistant roles)
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096)

    # Run inference in a thread to avoid blocking the event loop
    loop = asyncio.get_running_loop()

    def _generate():
        with torch.no_grad():
            outputs = model.generate(
                inputs.input_ids,
                max_new_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                do_sample=request.temperature > 0,
                pad_token_id=tokenizer.eos_token_id,
            )
        return outputs

    outputs = await loop.run_in_executor(None, _generate)

    # Decode only the new tokens (skip the input prompt)
    input_len = inputs.input_ids.shape[1]
    generated_ids = outputs[0][input_len:]
    generated_text = tokenizer.decode(generated_ids, skip_special_tokens=True)

    response = ChatCompletionResponse(
        id=f"chatcmpl-{int(time.time())}",
        created=int(time.time()),
        model=request.model,
        choices=[
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": generated_text,
                },
                "finish_reason": "stop",
            }
        ],
        usage={
            "prompt_tokens": input_len,
            "completion_tokens": len(generated_ids),
            "total_tokens": input_len + len(generated_ids),
        },
    )

    logger.info(
        "Generated %d tokens from %d prompt tokens in %.2fs",
        len(generated_ids), input_len, time.time() - response.created,
    )

    return response