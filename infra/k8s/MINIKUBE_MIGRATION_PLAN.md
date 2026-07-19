# Minikube Migration Plan — Fraud Detection System

## Overview
Migrate Docker Compose deployment to Minikube (local Kubernetes) on macOS Monterey 12.7.6.

## Prerequisites
| Software | Status | Purpose |
|---|---|---|
| **Docker Desktop** | ✅ Already installed | Runs the Minikube cluster |
| **Minikube** | ✅ v1.38.1 installed | Local K8s cluster |
| **kubectl** | ✅ Already installed | Manage K8s resources |
| **Helm** | ✅ v4.2.3 installed | Package manager for K8s (optional, for advanced Ingress configs) |

- 4 CPU cores, 16GB RAM available

---

## Step 1 — Start Minikube
```bash
minikube start --driver=docker --cpus=4 --memory=7000m
```

## Step 2 — Verify Cluster
```bash
kubectl cluster-info
minikube status
```

---

## Step 3 — Create K8s Manifests

All files go under `infra/k8s/`.

### 3a. `namespace.yaml`
Creates `fraud-detection` namespace to isolate all resources.

### 3b. `configmap.yaml`
Shared environment variables:
| Key | Value |
|---|---|
| `QDRANT_HOST` | `qdrant` |
| `QDRANT_PORT` | `6333` |
| `MLFLOW_TRACKING_URI` | `http://mlflow:5000` |
| `ML_API_URL` | `http://fraud-ml-api:3000` |
| `LLM_BASE_URL` | `https://api.openai.com/v1` |
| `LLM_MODEL` | `gpt-4o-mini` |

### 3c. `secrets.yaml`
Placeholder secrets (fill in actual base64-encoded values):
- `LLM_API_KEY`
- `OPENAI_API_KEY`

### 3d. `mlflow.yaml`
- **Deployment**: Image `ghcr.io/mlflow/mlflow:v2.19.0`, port 5000
- **Service**: ClusterIP, port 5000 (exposed as 5001 via port-forward)
- **PVC**: 5GB at `/mlflow`
- Command: `mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:///mlflow.db --default-artifact-root /mlflow/artifacts`

### 3e. `qdrant.yaml`
- **StatefulSet**: Image `qdrant/qdrant:latest`, port 6333
- **Service**: ClusterIP, port 6333
- **PVC**: 5GB at `/qdrant/storage`

### 3f. `fraud-ml-api.yaml` (overwrite existing)
- **Deployment**: Image `fraud-ml-api:latest`, port 3000, `imagePullPolicy: Never`
- **Service**: ClusterIP, port 3000
- Env vars from ConfigMap: `MLFLOW_TRACKING_URI`

### 3g. `fraud-mcp-server.yaml`
- **Deployment**: Image `fraud-mcp-server:latest`, port 9000, `imagePullPolicy: Never`
- **Service**: ClusterIP, port 9000
- Env vars from ConfigMap: `QDRANT_HOST`, `QDRANT_PORT`, `OPENAI_API_KEY` (from secrets)

### 3h. `fraud-agent-service.yaml`
- **Deployment**: Image `fraud-agent-service:latest`, port 8000, `imagePullPolicy: Never`
- **Service**: ClusterIP, port 8000
- Env vars from ConfigMap + Secrets: `ML_API_URL`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `QDRANT_HOST`, `QDRANT_PORT`, `OPENAI_API_KEY`

### 3i. `ingress.yaml` (for Minikube NGINX Ingress)
- **Purpose**: Routes external HTTP/HTTPS traffic to the correct internal Service based on URL path
- **Controller**: NGINX Ingress Controller (built-in Minikube addon)

#### Step 3i-1 — Enable NGINX Ingress in Minikube
```bash
# Enable the built-in NGINX Ingress controller
minikube addons enable ingress

# Wait for the controller pod to be ready
kubectl -n ingress-nginx wait --for=condition=ready pod -l app.kubernetes.io/name=ingress-nginx --timeout=120s

# Verify it's running
kubectl -n ingress-nginx get pods
```

#### Path Routing Rules:

| URL Path | Forwards To | Service Endpoints |
|---|---|---|
| `/` | `fraud-agent-service:8000` | `GET /` health, `POST /investigate` |
| `/ml-api` | `fraud-ml-api:3000` | `POST /predict` (BentoML) |
| `/mcp` | `fraud-mcp-server:9000` | MCP tools at `/mcp` |
| `/mlflow` | `mlflow:5000` | MLflow UI |

#### Access via Ingress (alternative to port-forward):
Once NGINX Ingress is enabled, you can access services through a single endpoint:
```bash
# Get Minikube IP
minikube ip

# Add to /etc/hosts for domain-based routing
echo "$(minikube ip) fraud-detection.local" | sudo tee -a /etc/hosts

# Now access via:
# http://fraud-detection.local/investigate    → fraud-agent-service
# http://fraud-detection.local/ml-api/predict → fraud-ml-api
# http://fraud-detection.local/mcp           → fraud-mcp-server
# http://fraud-detection.local/mlflow        → MLflow UI
```

> **Note**: The ingress feature is optional for local development. The simpler alternative (port-forward) is covered in Step 6.

---

## Step 4 — Build Docker Images into Minikube
```bash
eval $(minikube docker-env)
docker build -t fraud-ml-api:latest -f fraud-ml-api/Dockerfile .
docker build -t fraud-mcp-server:latest -f fraud-mcp-server/Dockerfile .
docker build -t fraud-agent-service:latest -f fraud-agent-service/Dockerfile .
```

---

## Step 5 — Deploy to Minikube

Apply the namespace first, then everything else (this avoids "namespace not found" errors caused by alphabetical file ordering):

```bash
# Step 5a: Create the namespace first
kubectl apply -f infra/k8s/namespace.yaml

# Step 5b: Apply all other resources (namespace already exists, so no errors)
kubectl apply -f infra/k8s/

# Step 5c: Watch pods come up
kubectl -n fraud-detection get pods -w
```

---

## Step 6 — Port-Forward Services for Local Access
```bash
kubectl -n fraud-detection port-forward svc/fraud-agent-service 8000:8000 &
kubectl -n fraud-detection port-forward svc/fraud-ml-api 3000:3000 &
kubectl -n fraud-detection port-forward svc/mlflow 5001:5000 &
kubectl -n fraud-detection port-forward svc/qdrant 6333:6333 &
```

---

## Step 7 — Verification
```bash
curl http://localhost:8000/health   # fraud-agent-service
curl http://localhost:3000/health   # fraud-ml-api
curl http://localhost:5001/         # MLflow UI
curl http://localhost:6333/         # Qdrant
```

---

## Step 8 — Monitoring and Observability

After deployment, use these commands to inspect and monitor your resources in the `fraud-detection` namespace.

### Quick Reference Table

| What to View | Command |
|---|---|
| **All resources** | `kubectl -n fraud-detection get all` |
| **Pods** | `kubectl -n fraud-detection get pods` |
| **Pods with details** | `kubectl -n fraud-detection get pods -o wide` |
| **Services** | `kubectl -n fraud-detection get svc` |
| **Deployments** | `kubectl -n fraud-detection get deploy` |
| **StatefulSets** | `kubectl -n fraud-detection get sts` |
| **Ingress** | `kubectl -n fraud-detection get ingress` |
| **PersistentVolumeClaims** | `kubectl -n fraud-detection get pvc` |
| **ConfigMaps** | `kubectl -n fraud-detection get cm` |
| **Secrets** | `kubectl -n fraud-detection get secret` |
| **All namespaces** | `kubectl get pods -A` |
| **Web Dashboard** | `minikube dashboard` |

### Watch Changes in Real-Time

Add `-w` (watch) flag to any `get` command:
```bash
kubectl -n fraud-detection get pods -w
```

### View Pod Logs
```bash
# Logs from a specific pod
kubectl -n fraud-detection logs <pod-name>

# Stream logs live (follow)
kubectl -n fraud-detection logs -f <pod-name>

# Last 20 lines
kubectl -n fraud-detection logs <pod-name> --tail=20
```

### Describe a Resource (Detailed Info)
```bash
kubectl -n fraud-detection describe pod <pod-name>
kubectl -n fraud-detection describe svc <service-name>
```

### Exec Into a Pod (Debugging)
```bash
kubectl -n fraud-detection exec -it <pod-name> -- /bin/bash
```

### Expected Output (Healthy Cluster)
```
kubectl -n fraud-detection get all

NAME                                       READY   STATUS    RESTARTS   AGE
pod/fraud-agent-service-75c4c48487-m758x   1/1     Running   0          8m
pod/fraud-mcp-server-56cdd67fdb-rsdvh      1/1     Running   0          8m
pod/fraud-ml-api-57cbcc4cf-5h7cp           1/1     Running   0          8m
pod/fraud-ml-api-57cbcc4cf-gwgnf           1/1     Running   0          8m
pod/mlflow-6bdcd5776b-wbzwj                1/1     Running   0          8m
pod/qdrant-0                               1/1     Running   0          10m

NAME                          TYPE        CLUSTER-IP      PORT(S)             AGE
service/fraud-agent-service   ClusterIP   10.96.183.103   8000/TCP            8m
service/fraud-mcp-server      ClusterIP   10.96.189.51    9000/TCP            8m
service/fraud-ml-api          ClusterIP   10.99.124.92    3000/TCP            8m
service/mlflow                ClusterIP   10.96.61.102    5000/TCP            8m
service/qdrant                ClusterIP   10.103.194.72   6333/TCP,6334/TCP   10m

NAME                                  READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/fraud-agent-service   1/1     1            1           8m
deployment.apps/fraud-mcp-server      1/1     1            1           8m
deployment.apps/fraud-ml-api          2/2     2            2           8m
deployment.apps/mlflow                1/1     1            1           8m

NAME                                     READY   AGE
statefulset.apps/qdrant                  1/1     10m
```

---

## Files Summary

| File | Action |
|---|---|
| `infra/k8s/namespace.yaml` | **NEW** |
| `infra/k8s/configmap.yaml` | **NEW** |
| `infra/k8s/secrets.yaml` | **NEW** |
| `infra/k8s/mlflow.yaml` | **NEW** |
| `infra/k8s/qdrant.yaml` | **NEW** |
| `infra/k8s/fraud-ml-api.yaml` | **OVERWRITE** |
| `infra/k8s/fraud-mcp-server.yaml` | **NEW** |
| `infra/k8s/fraud-agent-service.yaml` | **NEW** |
| `infra/k8s/ingress.yaml` | **NEW** (for NGINX Ingress) |

No changes needed to `docker-compose.yaml`, Dockerfiles, or application code.