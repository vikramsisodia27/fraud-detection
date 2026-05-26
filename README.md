# Enterprise Fraud Detection Platform

## Overview

This project is a production-grade enterprise fraud detection platform using:

* MLflow
* BentoML
* LangGraph
* Anthropic Claude
* MCP Server
* FastAPI
* Docker
* Kubernetes
* Jenkins
* Qdrant Vector DB

---

# Architecture

```text
                ┌────────────────────┐
                │      MLflow        │
                │  Model Registry    │
                └─────────┬──────────┘
                          │
                          ▼

                ┌────────────────────┐
                │      Jenkins       │
                │     CI / CD        │
                └─────────┬──────────┘
                          │
     ┌────────────────────┼────────────────────┐
     ▼                    ▼                    ▼

┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ BentoML API  │  │ Agent Service│  │ MCP Server   │
│ Fraud Model  │  │ Claude AI    │  │ Enterprise   │
│              │  │ LangGraph    │  │ Tools        │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────────────┼─────────────────┘
                         │
                         ▼

                ┌────────────────────┐
                │      Qdrant        │
                │     Vector DB      │
                └────────────────────┘
```

---

# Prerequisites

Install:

* Python 3.11+
* Docker Desktop
* Docker Compose
* Kubernetes (optional)
* kubectl
* Jenkins (optional)
* Git

---

# Clone Project

```bash
git clone <your-repository-url>

cd fraud-platform
```

---

# Setup Environment Variables

Create `.env` file:

```bash
ANTHROPIC_API_KEY=your_anthropic_api_key
```

---

# Start MLflow

```bash
docker compose up mlflow
```

MLflow UI:

```text
http://localhost:5001
```

---

# Train Model

Move into ML API module:

```bash
cd fraud-ml-api
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run training:

```bash
python app/train.py
```

This will:

* Train fraud model
* Log metrics to MLflow
* Register model in MLflow Registry

---

# Validate Model

```bash
python app/validate_model.py
```

---

# Promote Model

```bash
python app/promote_model.py
```

This promotes model to:

```text
Production
```

inside MLflow Registry.

---

# Import Model into BentoML

```bash
python app/import_model.py
```

This imports MLflow model into BentoML local store.

---

# Start Complete Platform

Go to project root:

```bash
cd ..
```

Run:

```bash
docker compose up --build
```

This starts:

| Service           | Port |
| ----------------- | ---- |
| MLflow            | 5001 |
| BentoML Fraud API | 3000 |
| MCP Server        | 9000 |
| Agent Service     | 8000 |
| Qdrant            | 6333 |

---

# Verify Services

## Fraud API

```bash
curl http://localhost:3000
```

---

## MCP Server

```bash
curl http://localhost:9000/tools
```

---

## Agent Service

```bash
curl http://localhost:8000/docs
```

---

# Test Fraud Detection Flow

```bash
curl -X POST http://localhost:8000/investigate \
-H "Content-Type: application/json" \
-d '{
  "features": [
    1,2,3,4,5,6,7,8,9,10
  ]
}'
```

---

# End-to-End Execution Flow

```text
1. train.py trains fraud model
        │
        ▼

2. MLflow stores model version
        │
        ▼

3. validate_model.py validates model
        │
        ▼

4. promote_model.py promotes model
        │
        ▼

5. import_model.py imports model into BentoML
        │
        ▼

6. BentoML exposes prediction API
        │
        ▼

7. Agent Service calls Fraud API
        │
        ▼

8. Claude AI reasons on fraud risk
        │
        ▼

9. MCP tools invoked
        │
        ▼

10. Fraud case created
```

---

# Jenkins Pipeline

Jenkins pipeline stages:

```text
Checkout
    │
    ▼

Train Model
    │
    ▼

Validate Model
    │
    ▼

Promote Model
    │
    ▼

Import Model
    │
    ▼

Build Docker Images
    │
    ▼

Deploy Kubernetes
```

---

# Run Jenkins Pipeline

Open Jenkins:

```text
http://localhost:8080
```

Create Pipeline Job:

```text
fraud-platform-pipeline
```

Point to:

```text
infra/jenkins/Jenkinsfile
```

Run Build.

---

# Kubernetes Deployment

Apply manifests:

```bash
kubectl apply -f infra/k8s/
```

Verify:

```bash
kubectl get pods
```

---

# Stop Platform

```bash
docker compose down
```

---

# Production Recommendations

Recommended improvements:

* Redis caching
* Kafka event streaming
* OpenTelemetry tracing
* Prometheus monitoring
* Grafana dashboards
* ArgoCD GitOps
* Vault secret management
* RBAC security
* Istio service mesh
* Feature store
* Human approval workflow

---

# Future Enhancements

Possible enterprise additions:

* Multi-agent fraud orchestration
* RAG over historical fraud cases
* Real-time Kafka fraud scoring
* Streaming risk engine
* Auto model retraining
* Human-in-the-loop approvals
* AI explainability
* Adaptive fraud policies
