# Helm Deployment Management

## Overview

The fraud detection system is deployed on Kubernetes using **Helm** (v3+). A single umbrella chart at `infra/helm/fraud-detection/` manages all four services:

| Service | Kubernetes Resource | Scaling |
|---------|-------------------|---------|
| `fraud-agent-service` | Deployment + Service + HPA | 1–2 replicas (CPU > 70%) |
| `fraud-ml-api` | Deployment + Service | Fixed — 1 replica |
| `fraud-mcp-server` | Deployment + Service | Fixed — 1 replica |
| `qdrant` | StatefulSet + Service + PVC | Fixed — 1 replica |

Additionally, an **mlflow-infra** chart is available at `infra/helm/mlflow-infra/` for the MLflow tracking server (deployed independently).

---

## Chart Structure

```
infra/helm/fraud-detection/
├── Chart.yaml                      # Chart metadata (name, version, apiVersion)
├── values.yaml                     # DEFAULT values (base configuration)
│
├── templates/
│   ├── _helpers.tpl                # Shared Helm template helpers (labels, names)
│   ├── namespace.yaml              # Namespace resource
│   ├── configmap.yaml              # Non-sensitive env vars for all services
│   ├── secrets.yaml                # Sensitive env vars (API keys, tokens)
│   ├── ingress.yaml                # NGINX Ingress rules (external access)
│   │
│   ├── fraud-agent-service/
│   │   ├── deployment.yaml         # Agent Deployment (1–2 pods, 4 workers each)
│   │   ├── service.yaml            # ClusterIP Service (port 8000)
│   │   └── hpa.yaml                # HorizontalPodAutoscaler (CPU > 70%)
│   │
│   ├── fraud-ml-api/
│   │   ├── deployment.yaml         # ML API Deployment
│   │   └── service.yaml            # ClusterIP Service (port 3000)
│   │
│   ├── fraud-mcp-server/
│   │   ├── deployment.yaml         # MCP Server Deployment
│   │   └── service.yaml            # ClusterIP Service (port 9000)
│   │
│   ├── qdrant/
│   │   ├── statefulset.yaml        # Qdrant StatefulSet (persistent storage)
│   │   ├── service.yaml            # ClusterIP Service (ports 6333, 6334)
│   │   └── pvc.yaml                # PersistentVolumeClaim (5Gi)
│   │
│   └── tests/
│       └── test-connection.yaml    # Helm test pod (connectivity check)
│
├── values/
│   ├── minikube.yaml               # Overrides for local Minikube dev
│   └── production.yaml             # Overrides for production deployment
│
└── tests/                          # Chart test scripts (if any)
```

### Template Naming Convention

Each service has its own **subdirectory** under `templates/`:

```
templates/fraud-agent-service/
templates/fraud-ml-api/
templates/fraud-mcp-server/
templates/qdrant/
```

This keeps resources organized and makes it easy to find, add, or remove a service without touching unrelated templates.

---

## Values Hierarchy (Override Order)

Helm merges values in the following order (later values win):

```
1. values.yaml                       (chart defaults)
2. -f values/minikube.yaml           (environment override)
3. --set key=value                   (inline override — highest priority)
```

### Default values.yaml (base configuration)

Defined in `infra/helm/fraud-detection/values.yaml`:

```yaml
global:
  namespace: fraud-detection
  imageRegistry: "host.docker.internal:5000"
  imagePullPolicy: "Always"
  ingress:
    enabled: true
    host: "fraud-detection.local"
    className: "nginx"

agent:
  enabled: true
  name: "fraud-agent-service"
  replicas: 1
  image: "fraud-agent-service"
  tag: "latest"
  port: 8000
  resources:
    limits:
      cpu: "500m"
      memory: "512Mi"
    requests:
      cpu: "250m"
      memory: "256Mi"

# ... mlApi, mcpServer, qdrant, config, secrets sections follow
```

### Environment Override Files

| File | Purpose | imageRegistry | Notes |
|------|---------|---------------|-------|
| `values/minikube.yaml` | Local development | `host.docker.internal:5000` | Built-in Minikube registry |
| `values/production.yaml` | Production/Cloud | `<cloud-registry>/fraud-detection` | Prod registry + resource tuning |

### Inline Overrides (──set)

Override any value at install/upgrade time without modifying files:

```bash
helm upgrade --install fraud-detection infra/helm/fraud-detection \
  --set agent.replicas=2 \
  --set agent.resources.limits.cpu="1"
```

---

## Key Configuration Sections

### `agent` — Fraud Agent Service (Auto-Scaled)

```yaml
agent:
  enabled: true              # Set to false to skip deployment
  name: "fraud-agent-service"
  replicas: 1                # Initial replica count (HPA overrides this)
  image: "fraud-agent-service"
  tag: "latest"
  port: 8000
  resources:
    limits:
      cpu: "500m"            # Max 0.5 CPU core per pod
      memory: "512Mi"        # Max 512 MB RAM per pod
    requests:
      cpu: "250m"            # Guaranteed 0.25 CPU core
      memory: "256Mi"        # Guaranteed 256 MB RAM
```

> **Note:** The HPA (`hpa.yaml`) scales replicas between 1–2 based on CPU utilization exceeding 70%. The `replicas` field in `values.yaml` only sets the initial count — the HPA controller will adjust it at runtime.

### `config` — Non-Sensitive Environment Variables

```yaml
config:
  qdrantHost: "qdrant"                          # DNS name resolves to qdrant Service
  qdrantPort: "6333"
  mlApiUrl: "http://fraud-ml-api:3000"          # Cluster DNS to ML API
  llmBaseUrl: "https://api.openai.com/v1"
  llmModel: "gpt-4o-mini"
  mlflowTrackingUri: "http://mlflow.mlflow-infra.svc.cluster.local:5000"
```

These values are injected into pods via the `fraud-detection-config` ConfigMap.

### `secrets` — Sensitive Environment Variables

```yaml
secrets:
  llmApiKey: ""          # WARNING: Do NOT commit real values to VCS
  openaiApiKey: ""       # Set via --set or external secrets management
```

Injected into pods via the `fraud-detection-secrets` Secret resource.

---

## Deployment Commands

### 1. Prerequisites

Ensure you have:
- **Kubernetes cluster** running (Minikube, GKE, EKS, AKS, etc.)
- **Helm v3** installed (`helm version`)
- **NGINX Ingress Controller** installed (`kubectl get pods -n ingress-nginx`)
- **Container images** built and pushed to the registry

### 2. Build and Push Images

```bash
# Build images (from project root)
docker build -t host.docker.internal:5000/fraud-agent-service:latest -f fraud-agent-service/Dockerfile .
docker build -t host.docker.internal:5000/fraud-ml-api:latest -f fraud-ml-api/Dockerfile .
docker build -t host.docker.internal:5000/fraud-mcp-server:latest -f fraud-mcp-server/Dockerfile .

# Push to registry (Minikube internal registry)
docker push host.docker.internal:5000/fraud-agent-service:latest
docker push host.docker.internal:5000/fraud-ml-api:latest
docker push host.docker.internal:5000/fraud-mcp-server:latest
```

### 3. Install / Upgrade

#### First-time install (Minikube):

```bash
helm install fraud-detection infra/helm/fraud-detection \
  --values infra/helm/fraud-detection/values/minikube.yaml
```

#### Upgrade (make changes → re-apply):

```bash
helm upgrade fraud-detection infra/helm/fraud-detection \
  --values infra/helm/fraud-detection/values/minikube.yaml
```

#### Production deploy:

```bash
helm upgrade --install fraud-detection infra/helm/fraud-detection \
  --values infra/helm/fraud-detection/values/production.yaml \
  --set secrets.llmApiKey="sk-..." \
  --set secrets.openaiApiKey="sk-..."
```

### 4. Verify

```bash
# List releases
helm list -n fraud-detection

# Check pod status
kubectl get pods -n fraud-detection

# Check HPA status
kubectl get hpa -n fraud-detection

# Run Helm tests
helm test fraud-detection -n fraud-detection
```

### 5. Rollback

```bash
# Rollback to previous revision
helm rollback fraud-detection -n fraud-detection

# Rollback to a specific revision
helm rollback fraud-detection 2 -n fraud-detection

# View revision history
helm history fraud-detection -n fraud-detection
```

### 6. Uninstall

```bash
helm uninstall fraud-detection -n fraud-detection
```

---

## Auto-Scaling (HPA) — fraud-agent-service

The **HorizontalPodAutoscaler** is defined in `templates/fraud-agent-service/hpa.yaml`:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fraud-agent-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fraud-agent-service
  minReplicas: 1
  maxReplicas: 2
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### How It Works

| Condition | Action |
|-----------|--------|
| CPU ≤ 70% | 1 replica (idle/steady state) |
| CPU > 70% sustained | Scales up to 2 replicas |
| CPU drops below 70% | Scales down to 1 replica |
| CPU spikes briefly | No action (HPA has a cooldown period) |

### HPA Requirements

For the HPA to function correctly, the target Deployment **must** have CPU resource `requests` defined:

```yaml
resources:
  requests:
    cpu: "250m"    # ← Required for HPA metric calculation
```

Without this, the HPA cannot compute CPU utilization and will not scale. These are set in `values.yaml` under `agent.resources`.

### Monitoring HPA

```bash
# Watch HPA in real-time
kubectl get hpa -n fraud-detection -w

# Describe HPA for detailed metrics
kubectl describe hpa fraud-agent-service-hpa -n fraud-detection

# Example output:
# Reference:                    Deployment/fraud-agent-service
# Metrics:                      ( current / target )
#   resource cpu on pods:       45% / 70%
# Min replicas:                 1
# Max replicas:                 2
# Deployment pods:              1 current / 1 desired
```

---

## Multi-Agent Architecture & Pod Scaling

The `fraud-agent-service` runs a **LangGraph supervisor graph** that orchestrates four specialist agents sequentially:

```
POST /investigate
  ├── ML prediction (fraud-ml-api)
  ├── if score ≥ 0.70 →
  │     supervisor → bureau_agent
  │     supervisor → aml_agent
  │     supervisor → compliance_agent
  │     supervisor → case_agent  → FINISH
  └── return response
```

Each investigation makes **4 LLM calls** + **4 MCP tool calls** and can take several seconds.

### Scaling Strategy

- **Per-pod concurrency**: Each pod runs 4 Uvicorn workers (set in Dockerfile), handling up to 4 investigations concurrently
- **Horizontal scaling**: HPA adds a 2nd pod when CPU exceeds 70% — bringing total capacity to **8 concurrent investigations** across 2 pods
- **No state sharing**: Each pod maintains its own in-memory LangGraph state (`InMemoryCache`) — state is not shared between pods

### Limitation

The current architecture uses `InMemoryCache` for LLM response caching. If scaled to 2 pods, each pod has its own cache — duplicate LLM calls may occur across pods. For production with higher scale requirements, consider switching to a shared Redis cache (see `app/__init__.py`).

---

## Environment-Specific Deployments

### Minikube (Local Development)

```bash
# Start Minikube with ingress
minikube start
minikube addons enable ingress

# Build images inside Minikube's Docker daemon
eval $(minikube docker-env)
docker build -t fraud-agent-service:latest -f fraud-agent-service/Dockerfile .
# ... build other images ...

# Deploy
helm install fraud-detection infra/helm/fraud-detection \
  --values infra/helm/fraud-detection/values/minikube.yaml

# Add host entry
echo "$(minikube ip) fraud-detection.local" | sudo tee -a /etc/hosts

# Test
curl http://fraud-detection.local/health
```

### Production (GKE / EKS / AKS)

```bash
# Authenticate to your cluster (GKE example)
gcloud container clusters get-credentials fraud-detection-prod --region us-central1

# Push images to cloud registry
docker tag fraud-agent-service:latest gcr.io/my-project/fraud-agent-service:latest
docker push gcr.io/my-project/fraud-agent-service:latest

# Deploy with production values
helm upgrade --install fraud-detection infra/helm/fraud-detection \
  --values infra/helm/fraud-detection/values/production.yaml \
  --set global.imageRegistry="gcr.io/my-project" \
  --set secrets.llmApiKey="sk-..." \
  --set secrets.openaiApiKey="sk-..."
```

---

## Troubleshooting Common Issues

### Pod stuck in `Pending` / `CrashLoopBackOff`

```bash
# Check pod details
kubectl describe pod -n fraud-detection <pod-name>

# Check logs
kubectl logs -n fraud-detection <pod-name>

# Common causes:
# - Image not found in registry → rebuild/push image
# - Resource requests too high for node → reduce requests in values.yaml
# - Secret not set → helm upgrade --set secrets.llmApiKey=...
```

### HPA not scaling

```bash
# Check if metrics-server is running (required by HPA)
kubectl get pods -n kube-system | grep metrics-server

# Install metrics-server if missing (Minikube)
minikube addons enable metrics-server

# Verify resource requests are set on the deployment
kubectl describe deployment fraud-agent-service -n fraud-detection | grep -A5 Requests

# Check HPA events
kubectl describe hpa fraud-agent-service-hpa -n fraud-detection
```

### Ingress not routing

```bash
# Verify ingress controller is running
kubectl get pods -n ingress-nginx

# Check ingress resource
kubectl describe ingress -n fraud-detection

# Ensure hostname resolves correctly
curl -H "Host: fraud-detection.local" http://$(minikube ip)/health
```

---

## Adding a New Service

To add a new service (e.g., `fraud-notification-service`):

1. Create a new subdirectory: `templates/fraud-notification-service/`
2. Add `deployment.yaml` and `service.yaml` templates
3. Add configuration section to `values.yaml`:
   ```yaml
   notificationService:
     enabled: true
     name: "fraud-notification-service"
     replicas: 1
     image: "fraud-notification-service"
     tag: "latest"
     port: 7000
     resources:
       requests:
         cpu: "100m"
         memory: "128Mi"
       limits:
         cpu: "200m"
         memory: "256Mi"
   ```
4. Add environment variables to `configmap.yaml` and `secrets.yaml` templates
5. Add ingress route to `ingress.yaml` (if external access needed)
6. Optionally add `hpa.yaml` if the service needs auto-scaling

---

## Quick Reference

```bash
# Install
helm install fraud-detection infra/helm/fraud-detection --values infra/helm/fraud-detection/values/minikube.yaml

# Upgrade (after code/config changes)
helm upgrade fraud-detection infra/helm/fraud-detection --values infra/helm/fraud-detection/values/minikube.yaml

# Dry-run (validate without applying)
helm upgrade --dry-run fraud-detection infra/helm/fraud-detection --values infra/helm/fraud-detection/values/minikube.yaml

# View rendered templates
helm template fraud-detection infra/helm/fraud-detection --values infra/helm/fraud-detection/values/minikube.yaml

# List releases
helm list -n fraud-detection

# Rollback
helm rollback fraud-detection 2 -n fraud-detection

# Uninstall
helm uninstall fraud-detection -n fraud-detection