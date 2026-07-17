# -----------------------------------------------------------
# Local LLM inference server (CPU-compatible)
#
# Serves Qwen/Qwen2.5-0.5B-Instruct (0.5B params) with an
# OpenAI-compatible API (chat/completions).  The fraud-agent-service
# connects to this via LangChain's ChatOpenAI by pointing base_url at
# http://local-llm-service:8001/v1.
#
# Uses HuggingFace transformers directly (not vLLM — vLLM requires
# NVIDIA GPUs). Runs on CPU, ~350 MB download, ~1.5 GB RAM.
# Fully open-access — no Hugging Face token required.
# -----------------------------------------------------------

FROM python:3.11-slim

WORKDIR /app

ENV HF_HOME=/root/.cache/huggingface
ENV MODEL_NAME=Qwen/Qwen2.5-0.5B-Instruct

# -----------------------------------------------------------
# Install dependencies
# -----------------------------------------------------------
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir --no-input accelerate transformers huggingface_hub fastapi uvicorn pydantic

# -----------------------------------------------------------
# Download the model at build time
# -----------------------------------------------------------
RUN python3 -c "\
import os; \
from huggingface_hub import snapshot_download; \
model = os.environ['MODEL_NAME']; \
snapshot_download(model); \
print(f'{model} pre-cached OK')"

# -----------------------------------------------------------
# Copy the OpenAI-compatible API server
# -----------------------------------------------------------
COPY fraud-ml-api/infra/local-llm/server.py server.py

# -----------------------------------------------------------
# Start server
# -----------------------------------------------------------
EXPOSE 8001

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]