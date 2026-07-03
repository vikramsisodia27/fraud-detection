# Enterprise Fraud Detection Platform

A microservices platform that trains an ML fraud model, serves predictions,
and — when a transaction scores above a risk threshold — hands it off to a
LangGraph multi-agent investigation team that consults MCP-exposed tools
(credit bureau, AML, historical case context via RAG) and opens a case.

> **⚠️ Before you do anything else:** see [Security](#security---read-this-first) below.
> `docker-compose.yaml` currently contains a hardcoded, live-looking OpenAI API key.

---

## Security - read this first

`docker-compose.yaml` hardcodes an `OPENAI_API_KEY` value (in two places —
`fraud-mcp-server` and `fraud-agent-service`). If this repo has been pushed
anywhere, cloned, or shared:

1. **Revoke that key immediately** in the OpenAI dashboard and generate a new one.
2. Remove it from git history if it was ever committed (`git filter-repo` /
   BFG — a simple new commit is not enough, the key remains in history).
3. Replace both hardcoded lines with `${OPENAI_API_KEY}` and load it from a
   local `.env` file (see below), which should be in `.gitignore`.

```yaml
# docker-compose.yaml — do this instead
environment:
  - OPENAI_API_KEY=${OPENAI_API_KEY}
```

```bash
# .env  (create at repo root, keep out of git)
OPENAI_API_KEY=sk-...
```

Also note: **the platform runs on OpenAI (`ChatOpenAI`, `gpt-5-mini`, and
`text-embedding-3-small`), not Anthropic Claude**, despite the project
description below mentioning Claude. If Claude is intended as the reasoning
model, `agent.py`, `supervisor.py`, and `agents/_base.py` need to swap
`ChatOpenAI` for `ChatAnthropic`, and `embeddings.py` needs a non-OpenAI
embedding provider (OpenAI embeddings have no Anthropic equivalent, so
that piece would stay as-is or move to a different embedding model).

---

## Overview

Stack in actual use:

* **MLflow** — experiment tracking + model registry
* **BentoML** — model packaging + serving
* **LangGraph** — multi-agent orchestration (supervisor/specialist pattern)
* **OpenAI** (`gpt-5-mini` + `text-embedding-3-small`) — LLM reasoning and embeddings
* **MCP** (`mcp` SDK, `FastMCP`) — tool server + `langchain-mcp-adapters` client
* **FastAPI** — agent-service HTTP API
* **Qdrant** — vector store for customer document RAG
* **Docker / Docker Compose** — local orchestration

Referenced in the original docs but **not present in this codebase**:
Kubernetes manifests, Jenkins pipeline, Anthropic Claude integration. Treat
those sections as a roadmap, not as things you can run today — see
[Gaps vs. this codebase](#gaps-vs-this-codebase).

---

## Architecture

```text
                ┌────────────────────┐
                │      MLflow        │
                │  Model Registry    │
                └─────────┬──────────┘
                          │
                          ▼
                ┌────────────────────┐
                │   fraud-ml-api     │
                │  BentoML + sklearn │   ← train / validate / promote / import / serve
                │  RandomForest      │
                └─────────┬──────────┘
                          │ POST /predict
                          ▼
                ┌────────────────────┐
                │ fraud-agent-service│
                │  FastAPI           │   ← POST /investigate
                │  LangGraph         │
                │  Supervisor +      │
                │  4 specialists     │
                └─────────┬──────────┘
                          │ MCP (streamable-http)
                          ▼
                ┌────────────────────┐        ┌────────────────────┐
                │  fraud-mcp-server  │───────▶│      Qdrant        │
                │  FastMCP tools:    │        │  customer_documents │
                │  bureau_check      │        │  vector collection │
                │  aml_check         │        └────────────────────┘
                │  customer_context  │
                │  create_case       │
                └────────────────────┘
```

### Request flow (`POST /investigate`)

1. `fraud-agent-service` calls `fraud-ml-api` for a prediction (`fraud_client.py`).
2. If `fraud_score < 0.70` → returns the prediction only, no investigation.
3. If `fraud_score >= 0.70` → builds a prompt and runs the **LangGraph
   supervisor graph** (`supervisor.py`):
   - `supervisor` node (router LLM) decides who acts next
   - `bureau_agent` → calls MCP tool `bureau_check`
   - `aml_agent` → calls MCP tool `aml_check`
   - `compliance_agent` → calls MCP tool `customer_context` (RAG over Qdrant)
   - `case_agent` → calls MCP tool `create_case`, runs last, synthesizes
     the other three specialists' findings into the case payload
4. Each specialist is a **separately scoped ReAct agent** — it only has
   access to its one MCP tool, not the full toolset (see `agents/_base.py`).
   This is a deliberate improvement over the older single-agent design.

---

## Repository layout

```text
.
├── docker-compose.yaml        # orchestrates mlflow, qdrant, and all 3 services
├── bentofile.yaml             # BentoML build config (points at app.service:svc — see note below)
├── requirements.txt           # single shared requirements file for all 3 Dockerfiles
├── fraud-ml-api/
│   ├── Dockerfile
│   └── app/
│       ├── config.py           # MLFLOW_TRACKING_URI
│       ├── train.py            # trains RandomForestClassifier, logs to MLflow
│       ├── validate_model.py   # gate: accuracy >= 0.90 or raises
│       ├── promote_model.py    # transitions latest version to "Production" stage
│       ├── import_model.py     # imports MLflow "Production" model into BentoML store
│       ├── model_pipeline.py   # runs train → validate → promote → import in sequence
│       ├── service.py          # BentoML @bentoml.service — /predict endpoint
│       └── fraud_transactions.csv  # 5,000-row synthetic training set
├── fraud-mcp-server/
│   ├── Dockerfile
│   └── app/
│       ├── server.py           # FastMCP server — 5 tools, streamable-http on :9000
│       ├── vector/
│       │   ├── embeddings.py   # OpenAI text-embedding-3-small
│       │   ├── qdrant_client.py
│       │   └── rag_service.py  # RagService — retrieval, dedup, per-type capping
│       ├── services/
│       │   └── customer_context_service.py  # empty file — see Known issues
│       └── scripts/            # one-off setup / seeding scripts, not called by server.py
│           ├── create_collection.py
│           ├── customer_documents.py   # 6 hardcoded sample docs for CUST-1001
│           ├── load_documents.py       # embeds + upserts customer_documents.py into Qdrant
│           └── search_documents.py     # manual query script (uses host="localhost")
└── fraud-agent-service/
    ├── Dockerfile
    └── app/
        ├── api.py              # FastAPI app — GET /, POST /investigate
        ├── fraud_client.py     # calls fraud-ml-api /predict
        ├── mcp_client.py       # MultiServerMCPClient → fraud-mcp-server
        ├── agent.py            # single-agent ReAct implementation (kept, not wired in)
        ├── supervisor.py       # multi-agent supervisor graph (the one api.py actually uses)
        └── agents/
            ├── _base.py         # make_specialist() factory shared by all 4 specialists
            ├── bureau_agent.py
            ├── aml_agent.py
            ├── compliance_agent.py
            └── case_agent.py
```

---

## Prerequisites

* Python 3.11+
* Docker Desktop + Docker Compose
* An OpenAI API key with access to `gpt-5-mini` and `text-embedding-3-small`
* Git

---

## Setup

```bash
git clone <your-repository-url>
cd <repo>
```

Create `.env` at the repo root:

```bash
OPENAI_API_KEY=your_openai_api_key
```

Then fix `docker-compose.yaml` as described in
[Security](#security---read-this-first) if it hasn't been fixed already.

---

## Running the full platform

```bash
docker compose up --build
```

| Service            | Port | Notes                                   |
| ------------------ | ---- | ---------------------------------------- |
| MLflow             | 5001 | UI at http://localhost:5001              |
| Qdrant             | 6333 | REST/gRPC vector store                   |
| fraud-ml-api        | 3000 | BentoML prediction service — needs a model imported first (below) |
| fraud-mcp-server    | 9000 | MCP tools over streamable-http at `/mcp` |
| fraud-agent-service | 8000 | FastAPI — `/docs` for interactive OpenAPI |

`fraud-ml-api` will fail `/predict` calls until a model has actually been
trained, validated, promoted, and imported (see next section) — the compose
file starts the *service*, it doesn't run the *pipeline* for you.

---

## Model pipeline (train → validate → promote → import)

Run once (or whenever you want to retrain), against a running `mlflow`
container:

```bash
docker compose up -d mlflow
cd fraud-ml-api
pip install -r ../requirements.txt
cd app
python train.py            # trains RandomForest, logs run + registers "fraud-detector" v1
python validate_model.py   # fails loudly if accuracy < 0.90
python promote_model.py    # promotes latest version to the "Production" stage
python import_model.py     # imports the Production model into the local BentoML store
```

Or run all four as one step:

```bash
python model_pipeline.py
```

Check what BentoML has:

```bash
bentoml models list
```

Run the service directly (outside Docker, for iteration):

```bash
bentoml serve service:FraudDetectionService --reload
```

> **Note on `bentofile.yaml`:** it currently points to `app.service:svc`,
> but `service.py` defines the class `FraudDetectionService`, not a `svc`
> object — this file looks stale relative to the current service.py /
> Dockerfile CMD (`bentoml serve app.service:FraudDetectionService`) and
> should be updated if you rely on `bentoml build` rather than the
> Dockerfile.

---

## Seeding the RAG / vector store

`fraud-mcp-server`'s `customer_context` tool retrieves from Qdrant. The
collection isn't seeded automatically — run these once against a running
`qdrant` container (from `fraud-mcp-server/app/scripts/`):

```bash
cd fraud-mcp-server/app/scripts
python create_collection.py   # creates "customer_documents" (1536-dim, cosine)
python load_documents.py      # embeds + upserts the 6 sample docs for CUST-1001
```

Everything in `scripts/` is standalone tooling — `server.py` never imports
from this folder. `search_documents.py` is a manual debugging script and
hardcodes `host="localhost"` (won't resolve inside Docker's network — run
it from your host machine with Qdrant's port published, which
`docker-compose.yaml` already does).

Sample data only covers `CUST-1001`; querying `customer_context` for any
other customer ID will legitimately return "No historical information found".

---

## Verifying services

```bash
curl http://localhost:3000                       # fraud-ml-api
curl http://localhost:9000/mcp                    # fraud-mcp-server (MCP endpoint, not plain REST)
curl http://localhost:8000/docs                   # fraud-agent-service OpenAPI
```

## Test the full investigation flow

```bash
curl -X POST http://localhost:8000/investigate \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST-1001",
    "transaction_id": "TXN-0001",
    "features": [122058, 3, 1, 5, 12, 38, 0, 6730, 1, 0.85]
  }'
```

`features` must be a 10-element numeric vector matching the training
columns in `fraud_transactions.csv` (categoricals are label-encoded
positionally, not by name — see [Known issues](#known-issues--gaps)).
Use `customer_id: "CUST-1001"` to see a populated `customer_context` result,
since that's the only seeded customer.

If `fraud_score >= 0.70`, the response includes `agent_result` with the
supervisor graph's full message trace across all four specialists.

---

## Known issues / gaps

**Security**
- Hardcoded OpenAI key in `docker-compose.yaml` — see top of this file.
- No root-level `.gitignore`; only `fraud-ml-api/.gitignore` exists. The
  archive includes `__pycache__/*.pyc` files, which is a sign of the same
  gap in the actual git repo.

**Stub / placeholder tools** (`fraud-mcp-server/app/server.py`) — these are
explicitly flagged in the code as stubs, not accidental:
- `bureau_check` always returns `bureau_score=740, delinquencies=0`
- `aml_check` always returns `status="CLEAR"`
- `create_case` doesn't persist anywhere — returns `CASE-{transaction_id}`
  and logs, no case management system behind it

Any investigation the agent runs today will always see a clean bureau and
clean AML result. This is fine for demoing the orchestration but means the
"investigation" is not yet grounded in real signal.

**Dead / stale code**
- `fraud-mcp-server/app/services/customer_context_service.py` is an empty
  file. The real implementation lives in `app/vector/rag_service.py`
  (`RagService`) — this file is leftover scaffolding.
- `fraud-agent-service/app/agent.py` (single all-tools ReAct agent) is no
  longer imported by `api.py`, which uses `supervisor.py` instead. It's
  intentionally kept per its own docstring for A/B comparison, but nothing
  currently exercises it — worth deleting or moving to an `examples/` dir
  if it's not actively used, so it doesn't silently drift out of date.
- `bentofile.yaml` references `app.service:svc`, which doesn't match
  `service.py`'s actual `FraudDetectionService` class.

**Fragile / fixed logic**
- `service.py`'s fraud score fallback (when `predict_proba` isn't
  available) hardcodes `0.90`/`0.10` rather than a real probability — the
  reported `risk_level` in that path is not actually calibrated.
- `FRAUD_SCORE_THRESHOLD = 0.70` in `api.py` is a hardcoded module
  constant, not configurable via environment variable.
- `train.py` label-encodes categorical columns with a fresh
  `LabelEncoder` fit at train time; nothing persists that encoder, so
  `service.py`'s `/predict` expects raw pre-encoded feature vectors from
  the caller with no guarantee they use the same encoding — a real
  production version would persist and reuse the fitted encoders (or move
  to a `Pipeline`/`ColumnTransformer`) so training and serving stay in sync.

**Packaging**
- All three services share one root `requirements.txt` and each
  `Dockerfile` installs the whole thing — `fraud-ml-api`'s image ends up
  with `langchain`, `langgraph`, `mcp`, etc. installed even though it never
  imports them, and vice versa for the other two services with
  `scikit-learn`. Splitting into `fraud-ml-api/requirements.txt`,
  `fraud-mcp-server/requirements.txt`, `fraud-agent-service/requirements.txt`
  would shrink each image and make dependency drift visible per service.

**Docs vs. code mismatch** (in the original README, now corrected above)
- Claimed Anthropic Claude integration — actual code uses OpenAI throughout.
- Claimed Jenkins pipeline (`infra/jenkins/Jenkinsfile`) — not present in
  this archive.
- Claimed Kubernetes manifests (`infra/k8s/`) — not present in this archive.
- `curl http://localhost:9000/tools` in the original doc doesn't work
  against a FastMCP streamable-http server the way a plain REST endpoint
  would — corrected above to `/mcp`.

---

## Gaps vs. this codebase

These were present in the original README's "Production Recommendations" /
"Future Enhancements" sections and remain genuinely not-yet-built (kept
here as an honest roadmap rather than implied-done):

* Jenkins CI/CD pipeline and Kubernetes manifests
* Redis caching, Kafka event streaming, OpenTelemetry tracing
* Prometheus / Grafana monitoring
* ArgoCD GitOps, Vault secret management, RBAC, Istio service mesh
* Feature store, human-in-the-loop approval workflow
* Real bureau/AML/case-management vendor integrations behind the MCP stubs
* Auto model retraining, adaptive fraud policies, AI explainability

---

## Stopping the platform

```bash
docker compose down
```
