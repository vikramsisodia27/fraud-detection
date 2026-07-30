# Kubernetes Concepts Reference

## Table of Contents
1. [Understanding Ports in Kubernetes](#1-understanding-ports-in-kubernetes)
2. [DNS in Kubernetes](#2-dns-in-kubernetes)
3. [Minikube vs AWS EKS](#3-minikube-vs-aws-eks)
4. [K8s Resource Types Summary](#4-k8s-resource-types-summary)

---

## 1. Understanding Ports in Kubernetes

### 1.1 Container Port (in Deployment/StatefulSet)

```yaml
# Inside Deployment → template → spec → containers
containers:
  - name: mlflow
    ports:
      - containerPort: 5000    # ← Port the app INSIDE the container listens on
```

- **What it is**: A declaration that the application inside the container is listening on this port
- **It is INFORMATIONAL** — it tells Kubernetes what the container does
- **The actual binding happens in the application code** (e.g., `mlflow server --port 5000`)
- **In Docker Compose equivalent**: This is the `CONTAINER_PORT` in `"host_port:container_port"`

### 1.2 Service Port and TargetPort

```yaml
kind: Service
metadata:
  name: mlflow
spec:
  ports:
    - port: 5000              # ← SERVICE PORT: what other services dial
      targetPort: 5000        # ← TARGET PORT: where traffic goes inside the pod
```

| Field | Purpose | Analogy |
|---|---|---|
| `port` | The port the Service listens on. Other pods use `mlflow:5000` | **Reception desk number** |
| `targetPort` | The port on the pod where traffic is forwarded | **Employee's direct line** |

### 1.3 How Traffic Flows

```
Other Pod                     Service                        Pod
─────────                    ────────                       ──────

fraud-agent-service          mlflow                         mlflow container
       │                        │                              │
       │  http://mlflow:5000    │                              │
       ├───────────────────────▶│                              │
       │                        │  targetPort: 5000            │
       │                        ├─────────────────────────────▶│
       │                        │                              │
       │                        │                              │ app listens on
       │                        │                              │ containerPort: 5000
       │                        │                              │
```

### 1.4 Port Mapping: Docker Compose vs Kubernetes

```yaml
# ─── Docker Compose ─────────────────────────────────────────────
ports:
  - "5001:5000"
#    │      │
#    │      └── CONTAINER_PORT (what the app listens on)
#    └── HOST_PORT (what you type in browser: localhost:5001)

# ─── Kubernetes Service ─────────────────────────────────────────
ports:
  - port: 5000           # SERVICE_PORT (what other pods use: mlflow:5000)
    targetPort: 5000     # TARGET_PORT (must match container's port)
```

**They don't have to match** — you can remap ports:

```yaml
# Service definition
ports:
  - port: 8080            # Other pods call: mlflow:8080
    targetPort: 5000       # Container still listens on port 5000
```

```
Other pod ──▶ mlflow:8080 ──▶ Service port 8080 ──▶ targetPort 5000 ──▶ containerPort 5000
```

### 1.5 Access from Your Machine (Port-Forward)

Since Kubernetes doesn't expose services to your host machine by default:

```bash
kubectl port-forward svc/mlflow 5001:5000
#                    local_port : service_port
```

Now `http://localhost:5001` → Service port 5000 → container port 5000.

### 1.6 Comparison Table

| Concept | Docker Compose | Kubernetes Service |
|---|---|---|
| What others use to reach this service | `HOST_PORT` (e.g. `5001`) | `port` (e.g. `5000`) |
| What the container actually listens on | `CONTAINER_PORT` (e.g. `5000`) | `targetPort` (e.g. `5000`) |
| Access from your machine | `localhost:5001` (direct) | `kubectl port-forward svc/mlflow 5001:5000` |
| Access from other services | N/A (single network) | `mlflow:5000` (DNS by service name) |

---

## 2. DNS in Kubernetes

### 2.1 How Internal DNS Works

Kubernetes runs **CoreDNS** — a built-in DNS server that automatically creates DNS records for every Service.

```yaml
kind: Service
metadata:
  name: mlflow               # ← This becomes the DNS name
  namespace: fraud-detection
```

Full DNS record: `mlflow.fraud-detection.svc.cluster.local`

Short form (within same namespace): `mlflow`

### 2.2 How Services Find Each Other (Same Namespace)

When services are in the same namespace, you can use the short DNS name:

```yaml
ML_API_URL: "http://fraud-ml-api:3000"
# Resolves to: fraud-ml-api.fraud-detection.svc.cluster.local:3000
```

### 2.3 How Services Find Each Other (Cross-Namespace)

When services are in different namespaces, you must use the fully-qualified DNS name:

```
<service>.<namespace>.svc.cluster.local:<port>
```

Example:
```yaml
MLFLOW_TRACKING_URI: "http://mlflow.mlflow-infra.svc.cluster.local:5000"
#               service    namespace
```

In your project, most DNS names are configured in the ConfigMap. `MLFLOW_TRACKING_URI` is hardcoded in `fraud-ml-api.yaml` since it's the only consumer:

| Where | Value | Resolves to | Namespace |
|---|---|---|---|
| `infra/k8s/fraud-ml-api.yaml` (hardcoded `env.value`) | `http://mlflow.mlflow-infra.svc.cluster.local:5000` | mlflow | mlflow-infra |
| ConfigMap key `ML_API_URL` | `http://fraud-ml-api:3000` | fraud-ml-api | fraud-detection |
| ConfigMap key `QDRANT_HOST` | `qdrant` | qdrant | fraud-detection |
| ConfigMap key `FRAUD_MCP_SERVER` | `http://fraud-mcp-server:9000` | fraud-mcp-server | fraud-detection |
| ConfigMap key `FRAUD_AGENT_SERVICE` | `http://fraud-agent-service:8000` | fraud-agent-service | fraud-detection |

### 2.4 Service Discovery Flow

```
┌──────────────────────────────────────────────────────────┐
│                   Kubernetes Cluster                      │
│                                                          │
│   ┌──────────────────────────────────────────┐            │
│   │  namespace: fraud-detection               │            │
│   │                                           │            │
│   │  fraud-agent-service                      │            │
│   │      │── http://fraud-ml-api:3000 ───▶ fraud-ml-api   │
│   │      │── http://fraud-mcp-server:9000 ─▶ MCP Server   │
│   │      │── grpc://qdrant:6333 ──────────▶ Qdrant        │
│   │                                           │            │
│   │  fraud-ml-api                             │            │
│   │      │── http://mlflow.mlflow-infra       │            │
│   │      │   .svc.cluster.local:5000          │            │
│   └──────────────────────────────────────────┘            │
│                    │                                      │
│                    │ (cross-namespace DNS)                │
│                    ▼                                      │
│   ┌──────────────────────────────────────────┐            │
│   │  namespace: mlflow-infra                  │            │
│   │                                           │            │
│   │  mlflow:5000 (tracking server)            │            │
│   │                                           │            │
│   │  Secrets: mlflow-infra-secrets            │            │
│   │  (duplicated for namespace isolation)     │            │
│   └──────────────────────────────────────────┘            │
│                                                          │
│   CoreDNS resolves all these names automatically         │
└──────────────────────────────────────────────────────────┘
```

### 2.5 Cross-Namespace Secrets

Kubernetes **Secrets are namespace-scoped**. A Secret in one namespace cannot be referenced by a pod in another namespace. This means:

```
✅ Pod in fraud-detection can use Secret fraud-detection-secrets
✅ Pod in mlflow-infra can use Secret mlflow-infra-secrets
❌ Pod in mlflow-infra CANNOT use Secret fraud-detection-secrets
```

**Solution**: Duplicate the required secrets into each namespace:

| Namespace | Secret Name | File |
|---|---|---|
| `fraud-detection` | `fraud-detection-secrets` | `infra/k8s/secrets.yaml` |
| `mlflow-infra` | `mlflow-infra-secrets` | `infra/k8s/secrets-mlflow-infra.yaml` |

> **Note**: Currently MLflow (the only service in `mlflow-infra`) does **not** require any API keys. The secret is provided for future services deployed in that namespace.

**Key point**: CoreDNS handles this identically in Minikube, EKS, or any Kubernetes cluster.

---

## 3. Minikube vs AWS EKS

### 3.1 Same — Internal DNS and Networking

All of these work **exactly the same** in Minikube and EKS:

- ✅ CoreDNS — `mlflow:5000` resolves the same way
- ✅ Services — ClusterIP, port/targetPort mapping
- ✅ Deployments, StatefulSets, ConfigMaps, Secrets
- ✅ PVCs and storage mounting
- ✅ Pod-to-pod communication

### 3.2 Different — External Access

| Aspect | Minikube (Local Dev) | AWS EKS (Production) |
|---|---|---|
| **Internal DNS** | CoreDNS (`mlflow:5000`) | CoreDNS (same: `mlflow:5000`) |
| **External DNS** | None — use port-forward | Route53 (your domain) |
| **How you access** | `kubectl port-forward svc/fraud-agent-service 8000:8000` then `localhost:8000` | ALB Ingress with Route53: `https://fraud-api.mycompany.com` |
| **Who can access** | Only you (localhost tunnel) | Any client on the internet |
| **TLS/SSL** | No | Yes (ACM certificate on ALB) |
| **Load balancing** | None needed | ALB (Application Load Balancer) |
| **Scaling** | Single node | Auto-scaling node groups |
| **Cost** | Free (runs on your Mac) | Pay-as-you-go |

### 3.3 Minikube Access Pattern

```
Your Mac
  │
  │ kubectl port-forward svc/fraud-agent-service 8000:8000
  │
  ▼
┌─────────────────────────────────────┐
│  Minikube (single node)             │
│                                     │
│  CoreDNS ──▶ mlflow:5000           │
│            ──▶ fraud-ml-api:3000   │
│            ──▶ fraud-mcp-server:9000│
│            ──▶ qdrant:6333         │
└─────────────────────────────────────┘
```

### 3.4 AWS EKS Access Pattern

```
Internet
  │
  │ https://fraud-api.mycompany.com
  ▼
AWS Route53 (DNS management)
  │
  │ A record → ALB DNS name
  ▼
AWS ALB (Application Load Balancer)
  │
  │ Routes based on Ingress rules
  ▼
┌─────────────────────────────────────┐
│  EKS Cluster                        │
│                                     │
│  Ingress Resource                   │
│    │                                │
│    └──▶ fraud-agent-service:8000   │
│                                     │
│  CoreDNS ──▶ mlflow:5000           │
│            ──▶ fraud-ml-api:3000   │
│            ──▶ fraud-mcp-server:9000│
│            ──▶ qdrant:6333         │
└─────────────────────────────────────┘
```

### 3.5 What You'd Need for EKS

For EKS, you would add an **Ingress** resource:

```yaml
# Example: infra/k8s/ingress.yaml (for EKS only)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: fraud-detection-ingress
  namespace: fraud-detection
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:...  # TLS cert
spec:
  rules:
    - host: fraud-api.mycompany.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: fraud-agent-service
                port:
                  number: 8000
```

This tells AWS: *"Route `fraud-api.mycompany.com → ALB → fraud-agent-service:8000`"*

---

## 4. K8s Resource Types Summary

### 4.1 Resources in This Project

| Resource | Kind | Purpose |
|---|---|---|
| Namespace | `Namespace` | Logical isolation for all resources |
| ConfigMap | `ConfigMap` | Non-sensitive env vars (URLs, ports, model names) |
| Secret | `Secret` | Sensitive data (API keys — base64 encoded) |
| PersistentVolumeClaim | `PersistentVolumeClaim` | Requests persistent disk storage |
| Deployment | `Deployment` | Runs stateless containers with auto-restart |
| StatefulSet | `StatefulSet` | Runs stateful containers (databases) with stable identity |
| Service | `Service` | Stable DNS endpoint for pod communication |

### 4.2 Understanding Two Specs in a Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mlflow
spec:                    # ← SPEC #1: DEPLOYMENT SPEC (how to manage pods)
  replicas: 1            #   Keep 1 pod running
  selector:              #   How to find my pods
    matchLabels:
      app: mlflow
  template:              # ← TEMPLATE STARTS (blueprint for pods)
    metadata:
      labels:
        app: mlflow
    spec:                # ← SPEC #2: POD SPEC (what goes inside each pod)
      containers:
        - name: mlflow
          image: ...
```

Think of it as:

```
Deployment = Factory Manager
  ├── Spec #1 (Deployment): "I need 1 worker, wearing 'app: mlflow' badge"
  └── Template = Job Description
       └── Spec #2 (Pod): "Worker should run this container image, mount this storage"
```

### 4.3 Volume and VolumeMounts

```yaml
# Step 1: PVC — Request storage from the cluster
kind: PersistentVolumeClaim
metadata:
  name: mlflow-pvc
spec:
  storage: 5Gi

# Step 2: volumes — Declare storage sources available to the pod
spec:
  volumes:
    - name: mlflow-storage          # Local name
      persistentVolumeClaim:
        claimName: mlflow-pvc       # Connect to PVC

# Step 3: volumeMounts — Attach storage inside the container
  containers:
    - name: mlflow
      volumeMounts:
        - name: mlflow-storage      # Must match volume name
          mountPath: /mlflow        # Path inside container
```

Analogy:
- **PVC** = "Hotel, I need a safety deposit box (5GB)"
- **volumes** = "Here's the box, I'll call it `mlflow-storage`"
- **volumeMounts** = "Put the box in room `/mlflow` inside the container"

---

*Document created for the Fraud Detection System Minikube migration project.*