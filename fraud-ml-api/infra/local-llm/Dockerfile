# -----------------------------------------------------------
# Local LLM inference server using vLLM
#
# Serves "microsoft/Phi-3-mini-4k-instruct" (3.8B params) with an
# OpenAI-compatible API (chat/completions).  The fraud-agent-service
# connects to this via LangChain's ChatOpenAI by pointing base_url at
# http://local-llm-service:8001/v1.
#
# Quantization: 4-bit (AWQ or GPTQ) reduces memory to ~3 GB.
# Hardware: CPU-only works (slow); GPU (NVIDIA T4+) recommended.
# -----------------------------------------------------------

FROM vllm/vllm-openai:latest

# -----------------------------------------------------------
# Download the model at build time
# -----------------------------------------------------------
ENV HF_HOME=/root/.cache/huggingface
RUN python3 -c "\
from huggingface_hub import snapshot_download; \
snapshot_download('microsoft/Phi-3-mini-4k-instruct'); \
print('Phi-3 model pre-cached OK')"

# -----------------------------------------------------------
# Start vLLM with OpenAI-compatible API
# -----------------------------------------------------------
EXPOSE 8001

ENTRYPOINT ["python3", "-m", "vllm.entrypoints.openai.api_server"]

CMD ["--model", "microsoft/Phi-3-mini-4k-instruct", "--port", "8001", "--host", "0.0.0.0", "--max-model-len", "4096", "--gpu-memory-utilization", "0.90", "--dtype", "auto"]