# Minikube Helm Deployment Guide

This guide documents the **complete end-to-end process** of deploying the fraud-detection application on **Minikube** using **Helm**, including how to stop Minikube and restart from the same position.

---

## 1. Architecture Overview

The application consists of **5 containers** deployed across **2 namespaces**:

| Service | Namespace | Container | Port | Type |
|---------|-----------|-----------|------|------|
| `fraud-agent-service` | fraud-detection | fraud-agent-service | 8000 | Deployment + HPA |
| `fraud-ml-api` | fraud-detection | fraud-ml-api | 3000 | Deployment |
| `fraud-mcp-server` | fraud-detection | fraud-mcp-server | 9000 | Deployment |
| `qdrant` | fraud-detection | qdrant | 6333/6334 | StatefulSet |
| `mlflow` | mlflow-infra | mlflow | 5000 | Deployment |

**Helm charts:**
- `infra/helm/fraud-detection/` — umbrella chart for the 4 core services
- `infra/helm/mlflow-infra/` — MLflow tracking server chart

---

## 2. Prerequisites

Ensure the following tools are installed:

```bash
# Verify versions
minikube version
kubectl version --client
helm version
docker --version
```

---

## 3. Start Minikube (2 Nodes)

> **Note:** Port `5000` is often occupied on macOS (AirPlay Receiver). We use a **local Docker registry on port `5001`** instead of Minikube's built-in registry.

### 3.1 Start the cluster

```bash
# Start Minikube with 2 nodes, 4 CPUs, 7GB memory
# --insecure-registry tells containerd to trust the local registry over HTTP
minikube start \
  --driver=docker \
  --cpus=4 \
  --memory=7000m \
  --nodes=2 \
  --insecure-registry="host.docker.internal:5001"
```

### 3.2 Verify nodes are ready

```bash
kubectl get nodes
# NAME           STATUS   ROLES           VERSION
# minikube       Ready    control-plane   v1.35.1
# minikube-m02   Ready    <none>          v1.35.1
```

### 3.3 Enable required addons

```bash
# NGINX Ingress Controller (for external access)
minikube addons enable ingress

# Metrics Server (required for HPA auto-scaling)
minikube addons enable metrics-server

# Verify addons are enabled
minikube addons list | grep -E "ingress |metrics-server"
```

---

## 4. Set Up Local Docker Registry

Since port `5000` is occupied, we run a local registry on port `5001`.

### 4.1 Start the registry container

```bash
docker run -d \
  --name local-registry \
  -p 5001:5000 \
  --restart=always \
  registry:2
```

### 4.2 Verify the registry is running

```bash
curl -s http://localhost:5001/v2/_catalog
# {"repositories":[]}
```

---

## 5. Build and Push Docker Images

### 5.1 Build the images

```bash
# From project root
docker build -t host.docker.internal:5001/fraud-agent-service:latest -f fraud-agent-service/Dockerfile .
docker build -t host.docker.internal:5001/fraud-ml-api:latest -f fraud-ml-api/Dockerfile .
docker build -t host.docker.internal:5001/fraud-mcp-server:latest -f fraud-mcp-server/Dockerfile .
```

### 5.2 Push to the local registry

```bash
docker push host.docker.internal:5001/fraud-agent-service:latest
docker push host.docker.internal:5001/fraud-ml-api:latest
docker push host.docker.internal:5001/fraud-mcp-server:latest
```

### 5.3 Verify images are in the registry

```bash
curl -s http://localhost:5001/v2/_catalog
# {"repositories":["fraud-agent-service","fraud-mcp-server","fraud-ml-api"]}
```

---

## 6. Configure Minikube Values

The file `infra/helm/values/minikube.yaml` contains environment-specific overrides.

### 6.1 Key settings

```yaml
global:
  namespace: fraud-detection
  imageRegistry: "host.docker.internal:5001"   # ← local registry on port 5001
  imagePullPolicy: "Always"
  ingress:
    enabled: true
    host: "fraud-detection.local"
    className: "nginx"

agent:
  replicas: 1
  resources:
    limits:
      cpu: "1000m"
      memory: "2Gi"        # ← Increased from 512Mi to fix OOMKilled
    requests:
      cpu: "500m"
      memory: "1Gi"
```

> **Important:** The `fraud-agent-service` was getting **OOMKilled** with the default `512Mi` memory limit. It was increased to `2Gi` in the minikube values file.

---

## 7. Deploy with Helm

### 7.1 Deploy the fraud-detection chart

```bash
cd /Users/vikramsisodia/Desktop/Learning/python/fraud-detection

helm install fraud-detection infra/helm/fraud-detection \
  --values infra/helm/values/minikube.yaml \
  --set secrets.llmApiKey="sk-..." \
  --set secrets.openaiApiKey="sk-..."
```

### 7.2 Deploy the mlflow-infra chart

```bash
helm install mlflow-infra infra/helm/mlflow-infra
```

### 7.3 Verify deployments

```bash
kubectl get pods -n fraud-detection
kubectl get pods -n mlflow-infra
```

Expected output — all pods `Running`:

```
fraud-detection   fraud-agent-service-xxx   1/1  Running
fraud-detection   fraud-ml-api-xxx          1/1  Running
fraud-detection   fraud-mcp-server-xxx      1/1  Running
fraud-detection   qdrant-0                  1/1  Running
mlflow-infra      mlflow-xxx                1/1  Running
```

---

## 8. Verify Services

### 8.1 Check services and endpoints

```bash
kubectl get svc -n fraud-detection
kubectl get endpoints -n fraud-detection
kubectl get ingress -n fraud-detection
kubectl get hpa -n fraud-detection
```

### 8.2 Test the services via port-forward

```bash
# Test fraud-ml-api (BentoML service)
kubectl port-forward -n fraud-detection svc/fraud-ml-api 3000:3000 &
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/livez   # 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/readyz  # 200

# Test fraud-agent-service (FastAPI)
kubectl port-forward -n fraud-detection svc/fraud-agent-service 8000:8000 &
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/        # 200

# Test mlflow
kubectl port-forward -n mlflow-infra svc/mlflow 5005:5000 &
curl -s -o /dev/null -w "%{http_code}" http://localhost:5005/        # 200
```

---

## 9. Model Pipeline (Required for Predictions)

The `/predict` endpoint returns an error until the model is registered and imported:

```
"no Models with name 'fraud-detector' exist in BentoML store"
```

To fix this, run these scripts **inside the fraud-ml-api pod** in order:

```bash
# Get the pod name
POD=$(kubectl get pods -n fraud-detection -l app=fraud-ml-api -o jsonpath='{.items[0].metadata.name}')

# 1. Train & register the model in MLflow
kubectl exec -n fraud-detection $POD -- python app/train.py

# 2. Promote the model to Production stage
kubectl exec -n fraud-detection $POD -- python app/promote_model.py

# 3. Import the model into the BentoML store
kubectl exec -n fraud-detection $POD -- python app/import_model.py
```

After step 3, the `/predict` endpoint will work and `/investigate` will no longer return "Prediction service unavailable".

---

## 10. Checking Containers on Nodes

### 10.1 All pods across all namespaces

```bash
kubectl get pods -A
```

### 10.2 Pods on the worker node (`minikube-m02`)

```bash
kubectl get pods -A -o wide --field-selector=spec.nodeName=minikube-m02
```

### 10.3 Pods on the control-plane node (`minikube`)

```bash
kubectl get pods -A -o wide --field-selector=spec.nodeName=minikube
```

### 10.4 Container names inside each pod

```bash
kubectl get pods -n fraud-detection \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\tcontainers: "}{.spec.containers[*].name}{"\n"}{end}'
```

---

## 11. Stopping Minikube

### 11.1 Stop the cluster (preserves all state)

```bash
minikube stop
```

This **stops** the VM/containers but **preserves**:
- All deployed Helm releases
- All pods, deployments, services, PVCs
- The local Docker registry container (separate from minikube)
- All data in persistent volumes

### 11.2 Verify it's stopped

```bash
minikube status
# minikube
# type: Control Plane
# host: Stopped
# kubelet: Stopped
# apiserver: Stopped
```

---

## 12. Restarting from the Same Position

### 12.1 Start Minikube again (same config)

```bash
# IMPORTANT: Use the SAME flags as the original start command
minikube start \
  --driver=docker \
  --cpus=4 \
  --memory=7000m \
  --nodes=2 \
  --insecure-registry="host.docker.internal:5001"
```

### 12.2 Verify the cluster is back up

```bash
kubectl get nodes
# Both nodes should be Ready
```

### 12.3 Verify addons are still enabled

```bash
minikube addons list | grep -E "ingress |metrics-server"
# Both should show "enabled"
```

### 12.4 Verify the local registry is still running

```bash
curl -s http://localhost:5001/v2/_catalog
# Should still list the 3 images
```

> If the registry container was stopped, restart it:
> ```bash
> docker start local-registry
> ```

### 12.5 Verify Helm releases are still deployed

```bash
helm list -n fraud-detection
helm list -n mlflow-infra
```

### 12.6 Verify pods come back up

```bash
kubectl get pods -n fraud-detection
kubectl get pods -n mlflow-infra
```

The pods will automatically restart because the Helm releases and their resources (Deployments, StatefulSets) are persisted in the cluster's etcd. **No re-deployment is needed.**

### 12.7 (Optional) Re-verify services

```bash
kubectl get svc -n fraud-detection
kubectl get ingress -n fraud-detection
kubectl get hpa -n fraud-detection
```

---

## 13. Full Stop → Clean Restart (Optional)

If you want to **completely tear down** and redeploy from scratch:

```bash
# 1. Uninstall Helm releases
helm uninstall fraud-detection -n fraud-detection
helm uninstall mlflow-infra -n mlflow-infra

# 2. Delete the minikube cluster entirely
minikube delete

# 3. (Optional) Remove the local registry
docker rm -f local-registry

# 4. Start fresh
minikube start --driver=docker --cpus=4 --memory=7000m --nodes=2 --insecure-registry="host.docker.internal:5001"
minikube addons enable ingress
minikube addons enable metrics-server

# 5. Restart registry (if removed)
docker run -d --name local-registry -p 5001:5000 --restart=always registry:2

# 6. Rebuild & push images (if registry was removed)
docker build -t host.docker.internal:5001/fraud-agent-service:latest -f fraud-agent-service/Dockerfile .
docker build -t host.docker.internal:5001/fraud-ml-api:latest -f fraud-ml-api/Dockerfile .
docker build -t host.docker.internal:5001/fraud-mcp-server:latest -f fraud-mcp-server/Dockerfile .
docker push host.docker.internal:5001/fraud-agent-service:latest
docker push host.docker.internal:5001/fraud-ml-api:latest
docker push host.docker.internal:5001/fraud-mcp-server:latest

# 7. Redeploy
helm install fraud-detection infra/helm/fraud-detection \
  --values infra/helm/values/minikube.yaml \
  --set secrets.llmApiKey="sk-..." \
  --set secrets.openaiApiKey="sk-..."
helm install mlflow-infra infra/helm/mlflow-infra
```

---

## 14. Troubleshooting

### Pod stuck in `ImagePullBackOff`

```bash
# Check the containerd registry config on the node
minikube ssh --node minikube-m02 "cat /etc/containerd/certs.d/host.docker.internal:5001/hosts.toml"
# Should show:
# server = "http://host.docker.internal:5001"
# [host."http://host.docker.internal:5001"]
#   skip_verify = true
```

### Pod `OOMKilled`

```bash
# Check the pod's memory limit
kubectl describe pod -n fraud-detection <pod-name> | grep -A5 Limits

# Fix: increase memory limit in infra/helm/values/minikube.yaml
# agent.resources.limits.memory: "2Gi"
# Then upgrade:
helm upgrade fraud-detection infra/helm/fraud-detection \
  --values infra/helm/values/minikube.yaml \
  --set secrets.llmApiKey="sk-..." \
  --set secrets.openaiApiKey="sk-..."
```

### HPA showing `<unknown>` targets

```bash
# Ensure metrics-server is running
kubectl get pods -n kube-system | grep metrics-server

# If not, enable it
minikube addons enable metrics-server
```

### Port 5000 already in use

```bash
# Check what's using port 5000
lsof -i :5000

# Use port 5001 for the registry instead (as documented above)
```

---

## 15. Quick Reference Commands

```bash
# Start minikube
minikube start --driver=docker --cpus=4 --memory=7000m --nodes=2 --insecure-registry="host.docker.internal:5001"

# Enable addons
minikube addons enable ingress
minikube addons enable metrics-server

# Start registry
docker run -d --name local-registry -p 5001:5000 --restart=always registry:2

# Build & push
docker build -t host.docker.internal:5001/fraud-agent-service:latest -f fraud-agent-service/Dockerfile .
docker push host.docker.internal:5001/fraud-agent-service:latest

# Deploy
helm install fraud-detection infra/helm/fraud-detection --values infra/helm/values/minikube.yaml --set secrets.llmApiKey="sk-..." --set secrets.openaiApiKey="sk-..."
helm install mlflow-infra infra/helm/mlflow-infra

# Upgrade
helm upgrade fraud-detection infra/helm/fraud-detection --values infra/helm/values/minikube.yaml --set secrets.llmApiKey="sk-..." --set secrets.openaiApiKey="sk-..."

# Stop / Restart
minikube stop
minikube start --driver=docker --cpus=4 --memory=7000m --nodes=2 --insecure-registry="host.docker.internal:5001"

# Verify
kubectl get pods -A
kubectl get svc -n fraud-detection
kubectl get ingress -n fraud-detection
kubectl get hpa -n fraud-detection
```
