# Minikube Migration Plan — Fraud Detection System

## Overview
Migrate Docker Compose deployment to Minikube (local Kubernetes) on macOS Monterey 12.7.6.

## Architecture
- **Minikube**: 2-node cluster (1 control-plane + 1 worker)
- **Registry**: External Docker registry running on host (`localhost:5000`)
- **Images**: Pushed to registry, pulled by Minikube via `host.docker.internal:5000`
- **Namespaces**:
  - `fraud-detection` — Application services (agent, ML API, MCP server, Qdrant)
  - `mlflow-infra` — MLflow tracking server (separated for lifecycle independence)
- **Replicas**:
  - `fraud-agent-service`: **1 replica**
  - `fraud-ml-api`: **1 replica**
  - `fraud-mcp-server`: **1 replica**
  - `mlflow`: **1 replica** (in `mlflow-infra` namespace)
  - `qdrant`: 1 replica (StatefulSet)

## Prerequisites
| Software | Status | Purpose |
|---|---|---|
| **Docker Desktop** | ✅ Already installed | Runs the Minikube cluster |
| **Minikube** | ✅ v1.38.1 installed | Local K8s cluster |
| **kubectl** | ✅ Already installed | Manage K8s resources |
| **Helm** | ✅ v4.2.3 installed | Package manager for K8s (optional, for advanced Ingress configs) |

- 2 CPU cores, 5GB RAM allocated

---

## Step 1 — Start Minikube with 1 Worker Node
```bash
# Start a 2-node cluster (1 control-plane + 1 worker)
minikube start --driver=docker --cpus=2 --memory=7000m --nodes=2

# Verify the nodes
kubectl get nodes
```

Expected output:
```
NAME                           STATUS   ROLES           AGE   VERSION
minikube                       Ready    control-plane   1m   v1.32.0
minikube-m02                   Ready    <none>          1m   v1.32.0
```

## Step 2 — Run Local Docker Registry
```bash
# Start a local Docker registry on your Mac
docker run -d -p 5000:5000 --name local-registry registry:2

# Verify it's running
curl http://localhost:5000/v2/_catalog
```
The registry runs at `localhost:5000` on your Mac. From within Minikube's Docker network, it's reachable at `host.docker.internal:5000`.

---

## Step 3 — Create K8s Manifests

All files go under `infra/k8s/`.

### 3a. `namespace.yaml`
Creates `fraud-detection` namespace to isolate all resources.

### 3b. `configmap.yaml`
Shared environment variables (in `fraud-detection` namespace):
| Key | Value | Notes |
|---|---|---|
| `QDRANT_HOST` | `qdrant` | Same namespace, short DNS works |
| `QDRANT_PORT` | `6333` | |
| `ML_API_URL` | `http://fraud-ml-api:3000` | Same namespace |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | |
| `LLM_MODEL` | `gpt-4o-mini` | |

> **Note**: `MLFLOW_TRACKING_URI` is no longer in ConfigMap. It's hardcoded in `fraud-ml-api.yaml` since `fraud-ml-api` is the only consumer. See 3h below.

### 3c. `secrets.yaml`
Placeholder secrets (in `fraud-detection` namespace):
- `LLM_API_KEY`
- `OPENAI_API_KEY`

### 3d. `namespace-mlflow.yaml`
Creates `mlflow-infra` namespace for MLflow tracking server.

### 3e. `mlflow-mlflow-infra.yaml`
MLflow tracking server deployed in the `mlflow-infra` namespace (separate from application services):
- **Deployment**: Image `ghcr.io/mlflow/mlflow:v2.19.0`, **1 replica**, port 5000
- **Service**: ClusterIP, port 5000 — accessible cross-namespace via `mlflow.mlflow-infra.svc.cluster.local:5000`
- **PVC**: 5GB at `/mlflow`
- Command: `mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:///mlflow.db --default-artifact-root /mlflow/artifacts`
- **No ConfigMap or Secrets needed** — MLflow is self-contained

### 3f. `secrets-mlflow-infra.yaml`
Duplicate secrets for the `mlflow-infra` namespace (Kubernetes Secrets are namespace-scoped):
- `LLM_API_KEY`
- `OPENAI_API_KEY`
- Currently unused by MLflow but provided for future services deployed in `mlflow-infra`

### 3g. `qdrant.yaml`
- **StatefulSet**: Image `qdrant/qdrant:latest`, port 6333
- **Service**: ClusterIP, port 6333
- **PVC**: 5GB at `/qdrant/storage`

### 3h. `fraud-ml-api.yaml`
- **Deployment**: **1 replica**, image `host.docker.internal:5000/fraud-ml-api:latest`, port 3000, `imagePullPolicy: Always`
- **Service**: ClusterIP, port 3000
- **`MLFLOW_TRACKING_URI`**: hardcoded as `http://mlflow.mlflow-infra.svc.cluster.local:5000` (cross-namespace DNS). Not in ConfigMap — `fraud-ml-api` is the only consumer.

### 3i. `fraud-mcp-server.yaml`
- **Deployment**: **1 replica**, image `host.docker.internal:5000/fraud-mcp-server:latest`, port 9000, `imagePullPolicy: Always`
- **Service**: ClusterIP, port 9000
- Env vars from ConfigMap: `QDRANT_HOST`, `QDRANT_PORT`, `OPENAI_API_KEY` (from secrets)

### 3j. `fraud-agent-service.yaml`
- **Deployment**: **1 replica**, image `host.docker.internal:5000/fraud-agent-service:latest`, port 8000, `imagePullPolicy: Always`
- **Service**: ClusterIP, port 8000
- Env vars from ConfigMap + Secrets: `ML_API_URL`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `QDRANT_HOST`, `QDRANT_PORT`, `OPENAI_API_KEY`

### 3k. `ingress.yaml` (for Minikube NGINX Ingress)
- **Purpose**: Routes external HTTP/HTTPS traffic to the correct internal Service based on URL path
- **Controller**: NGINX Ingress Controller (built-in Minikube addon)

#### Enable NGINX Ingress:
```bash
# Enable the built-in NGINX Ingress controller
minikube addons enable ingress

# Wait for the controller pod to be ready
kubectl -n ingress-nginx wait --for=condition=ready pod -l app.kubernetes.io/name=ingress-nginx --timeout=120s

# Verify it's running
kubectl -n ingress-nginx get pods
```

> **Note (MLflow Ingress removed)**: The `/mlflow` Ingress route has been removed because Ingress rules can only reference Services in the same namespace. MLflow is now in the `mlflow-infra` namespace. Access MLflow UI via port-forward instead (see Step 7).

#### Path Routing Rules:

| URL Path | Forwards To | Service Endpoints |
|---|---|---|
| `/` | `fraud-agent-service:8000` | `GET /` health, `POST /investigate` |
| `/ml-api` | `fraud-ml-api:3000` | `POST /predict` (BentoML) |
| `/mcp` | `fraud-mcp-server:9000` | MCP tools at `/mcp` |

#### Access via Ingress:
```bash
# Get Minikube IP
minikube ip

# Add to /etc/hosts for domain-based routing
echo "$(minikube ip) fraud-detection.local" | sudo tee -a /etc/hosts

# Now access via:
# http://fraud-detection.local/investigate    → fraud-agent-service
# http://fraud-detection.local/ml-api/predict → fraud-ml-api
# http://fraud-detection.local/mcp           → fraud-mcp-server
```

> **Note**: The ingress feature is optional for local development. The simpler alternative (port-forward) is covered in Step 7.

---

## Step 4 — Build & Push Docker Images to Local Registry
```bash
# Build images with the registry tag
docker build -t localhost:5000/fraud-ml-api:latest -f fraud-ml-api/Dockerfile .
docker build -t localhost:5000/fraud-mcp-server:latest -f fraud-mcp-server/Dockerfile .
docker build -t localhost:5000/fraud-agent-service:latest -f fraud-agent-service/Dockerfile .

# Push images to the local registry (running on your Mac at port 5000)
docker push localhost:5000/fraud-ml-api:latest
docker push localhost:5000/fraud-mcp-server:latest
docker push localhost:5000/fraud-agent-service:latest

# Verify images are in the registry
curl http://localhost:5000/v2/_catalog
```

Expected output:
```json
{"repositories":["fraud-agent-service","fraud-mcp-server","fraud-ml-api"]}
```

---

## Step 5 — Deploy to Minikube

Apply namespaces first, then everything else (this avoids "namespace not found" errors):

```bash
# Step 5a: Create both namespaces first
kubectl apply -f infra/k8s/namespace.yaml          # fraud-detection
kubectl apply -f infra/k8s/namespace-mlflow.yaml    # mlflow-infra

# Step 5b: Apply all other resources (namespaces already exist, so no errors)
kubectl apply -f infra/k8s/

# Step 5c: Watch pods come up in both namespaces
kubectl -n fraud-detection get pods -w &
kubectl -n mlflow-infra get pods -w
```

---

## Step 6 — Verify Pod Distribution on Worker Node
```bash
# Check which node each pod is running on
kubectl -n fraud-detection get pods -o wide

# Verify fraud-agent-service has 1 replica on the single worker node
kubectl -n fraud-detection get pods -l app=fraud-agent-service -o wide
```

Expected output (all pods should be scheduled on the single worker node):
```
NAME                                      READY   STATUS    RESTARTS   AGE   NODE
pod/fraud-agent-service-75c4c48487-a1b2c   1/1     Running   0          2m   minikube-m02
pod/fraud-mcp-server-56cdd67fdb-rsdvh      1/1     Running   0          2m   minikube-m02
pod/fraud-ml-api-57cbcc4cf-5h7cp           1/1     Running   0          2m   minikube-m02
pod/mlflow-6bdcd5776b-wbzwj                1/1     Running   0          2m   minikube-m02
pod/qdrant-0                               1/1     Running   0          2m   minikube-m02
```

---

## Step 7 — Port-Forward Services for Local Access

> **Note**: MLflow now lives in the `mlflow-infra` namespace, so its port-forward requires the `-n` flag.

```bash
kubectl -n fraud-detection port-forward svc/fraud-agent-service 8000:8000 &
kubectl -n fraud-detection port-forward svc/fraud-ml-api 3000:3000 &
kubectl -n mlflow-infra port-forward svc/mlflow 5001:5000 &
kubectl -n fraud-detection port-forward svc/qdrant 6333:6333 &
```

---

## Step 8 — Verification
```bash
curl http://localhost:8000/health   # fraud-agent-service
curl http://localhost:3000/health   # fraud-ml-api
curl http://localhost:5001/         # MLflow (in mlflow-infra namespace)
curl http://localhost:6333/         # Qdrant
```

---

## Step 9 — Monitoring and Observability

After deployment, use these commands to inspect and monitor your resources in the `fraud-detection` namespace.

### Quick Reference Table

| What to View | Command |
|---|---|
| **All resources** | `kubectl -n fraud-detection get all` |
| **Pods** | `kubectl -n fraud-detection get pods` |
| **Pods with node info** | `kubectl -n fraud-detection get pods -o wide` |
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
pod/fraud-agent-service-75c4c48487-a1b2c   1/1     Running   0          8m
pod/fraud-mcp-server-56cdd67fdb-rsdvh      1/1     Running   0          8m
pod/fraud-ml-api-57cbcc4cf-5h7cp           1/1     Running   0          8m
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
deployment.apps/fraud-ml-api          1/1     1            1           8m
deployment.apps/mlflow                1/1     1            1           8m

NAME                                     READY   AGE
statefulset.apps/qdrant                  1/1     10m
```

---

## Files Summary

| File | Action | Namespace |
|---|---|---|
| `infra/k8s/namespace.yaml` | **NEW** | — |
| `infra/k8s/configmap.yaml` | **MODIFIED** — `MLFLOW_TRACKING_URI` removed (now hardcoded in `fraud-ml-api.yaml`) | `fraud-detection` |
| `infra/k8s/secrets.yaml` | **NEW** | `fraud-detection` |
| `infra/k8s/mlflow.yaml.deprecated` | **RENAMED** — old single-namespace manifest, preserved for rollback reference | `fraud-detection` (disabled) |
| `infra/k8s/qdrant.yaml` | **NEW** | `fraud-detection` |
| `infra/k8s/fraud-ml-api.yaml` | **MODIFIED** — `MLFLOW_TRACKING_URI` hardcoded as `value:` (no ConfigMap lookup) | `fraud-detection` |
| `infra/k8s/fraud-mcp-server.yaml` | **NEW** — 1 replica, registry image | `fraud-detection` |
| `infra/k8s/fraud-agent-service.yaml` | **NEW** — 1 replica, registry image | `fraud-detection` |
| `infra/k8s/ingress.yaml` | **MODIFIED** — removed `/mlflow` route (cross-namespace not supported) | `fraud-detection` |
| `infra/k8s/namespace-mlflow.yaml` | **NEW** — creates `mlflow-infra` namespace | — |
| `infra/k8s/mlflow-mlflow-infra.yaml` | **NEW** — MLflow tracking server with 1 replica | `mlflow-infra` |
| `infra/k8s/secrets-mlflow-infra.yaml` | **NEW** — duplicate secrets for `mlflow-infra` namespace | `mlflow-infra` |

### Cross-Namespace Invocation Flow

```
fraud-agent-service (fraud-detection namespace)
  │
  ├── http://fraud-ml-api:3000/predict  ──► fraud-ml-api (same namespace)
  │                                            │
  │                                            └── loads model via
  │                                                http://mlflow.mlflow-infra.svc.cluster.local:5000
  │                                                (hardcoded in fraud-ml-api.yaml env.value)
  │
  └── returns prediction + fraud_score
```

> **No code changes in fraud-agent-service** — it only calls `fraud-ml-api:3000/predict` via `ML_API_URL` (unchanged). The `MLFLOW_TRACKING_URI` URL is hardcoded directly in `fraud-ml-api.yaml` — no ConfigMap lookup needed since `fraud-ml-api` is the only consumer.

### Cleanup (if reverting to single-namespace)
To move MLflow back to `fraud-detection` namespace:
1. Revert `MLFLOW_TRACKING_URI` in `configmap.yaml` to `http://mlflow:5000`
2. Delete `infra/k8s/namespace-mlflow.yaml`, `mlflow-mlflow-infra.yaml`, `secrets-mlflow-infra.yaml`
3. Restore the `/mlflow` Ingress route in `ingress.yaml`
4. Run: `kubectl delete ns mlflow-infra && kubectl apply -f infra/k8s/`

## Cleanup

### Stop Local Registry
```bash
docker stop local-registry && docker rm local-registry
```

### Stop Minikube
```bash
minikube stop
```

### Delete Minikube Cluster
```bash
minikube delete