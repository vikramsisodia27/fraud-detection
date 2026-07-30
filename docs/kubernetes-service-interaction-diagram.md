# Kubernetes Service Interaction Diagram

## Overview — Which Service Type Is Used?

**All internal services use `ClusterIP`** (internal-only access):

| Service | Type | Port | Exposed Externally? | How? | Scaling (HPA) |
|---|---|---|---|---|---|
| `fraud-agent-service` | **ClusterIP** | 8000 | ✅ Yes | Via **Ingress** (path `/`) | 1–2 replicas, CPU > 70% |
| `fraud-ml-api` | **ClusterIP** | 3000 | ✅ Yes | Via **Ingress** (path `/ml-api`) | Fixed — 1 replica |
| `fraud-mcp-server` | **ClusterIP** | 9000 | ✅ Yes | Via **Ingress** (path `/mcp`) | Fixed — 1 replica |
| `qdrant` | **ClusterIP** | 6333, 6334 | ✅ Yes | Via **Ingress** (path `/qdrant`) | Fixed — 1 replica (StatefulSet) |

**No services use NodePort.** All external access goes through the **NGINX Ingress Controller**.

---

## Interaction Diagram (ASCII)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             ☁️ OUTSIDE WORLD                                      │
│                                                                                  │
│              👤 User / Client (curl, Postman, App)                               │
│                                                                                  │
│   http://fraud-detection.local/investigate                                       │
│   http://fraud-detection.local/ml-api/predict                                    │
│   http://fraud-detection.local/mcp                                               │
│   http://fraud-detection.local/qdrant                                            │
└──────────────────────────┬───────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    🌐 INGRESS LAYER (NGINX Ingress Controller)                    │
│                                                                                  │
│                         ingress.yaml                                             │
│            networking.k8s.io/v1/Ingress                                          │
│                                                                                  │
│   ┌────────────┬────────────────┬─────────────────┬──────────────────────┐       │
│   │  Path: /   │  Path: /ml-api│   Path: /mcp    │   Path: /qdrant      │       │
│   │  Rewrite: /│  Rewrite: /$2 │   Rewrite: /$2   │   Rewrite: /$2       │       │
│   └──────┬─────┘──────┬────────┘───────┬──────────┘──────────┬───────────┘       │
│          │            │                │                     │                   │
└──────────┼────────────┼────────────────┼─────────────────────┼───────────────────┘
           │            │                │                     │
           ▼            ▼                ▼                     ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    📡 SERVICE LAYER — All ClusterIP                               │
│                                                                                  │
│  ┌──────────────────┐  ┌──────────────┐  ┌────────────────┐  ┌──────────────┐   │
│  │fraud-agent-      │  │fraud-ml-api  │  │fraud-mcp-server│  │qdrant        │   │
│  │service           │  │              │  │                │  │              │   │
│  │ClusterIP :8000   │  │ClusterIP:3000│  │ClusterIP :9000 │  │ClusterIP:6333│   │
│  │svc/fraud-agent-  │  │svc/fraud-ml-│  │svc/fraud-mcp-  │  │svc/qdrant:   │   │
│  │service:8000      │  │api:3000     │  │server:9000     │  │6333          │   │
│  └────────┬─────────┘  └──────┬───────┘  └────────┬───────┘  └──────┬────────┘   │
│           │                  │                    │                 │           │
└───────────┼──────────────────┼────────────────────┼─────────────────┼───────────┘
            │                  │                    │                 │
            ▼                  ▼                    ▼                 ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    🐳 POD / DEPLOYMENT LAYER                                      │
│                                                                                  │
│  ┌──────────────────┐  ┌──────────────┐  ┌────────────────┐  ┌──────────────┐   │
│  │🧠 fraud-agent-   │  │📊 fraud-ml-  │  │📄 fraud-mcp-   │  │🗄️ qdrant     │   │
│  │   service Pod    │  │   api Pod    │  │   server Pod   │  │   Pod        │   │
│  │                  │  │              │  │                │  │              │   │
│  │ Port: 8000      │  │ Port: 3000   │  │ Port: 9000     │  │Port: 6333    │   │
│  │                  │  │              │  │                │  │(gRPC)        │   │
│  │ Main             │  │ ML           │  │ RAG / Document │  │ Vector       │   │
│  │ Orchestrator     │  │ Predictions  │  │ Retrieval      │  │ Database     │   │
│  └──────────────────┘  └──────────────┘  └────────────────┘  └──────────────┘   │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘

                         INTER-SERVICE COMMUNICATION (Cluster DNS)
                         =========================================

    fraud-agent-service ──────────────────▶ fraud-ml-api
    (ML_API_URL)                               :3000
    ┌──────────────────────────────────────────► http://fraud-ml-api:3000 ──────────┐
    │                                                                              │
    fraud-agent-service ──────────────────▶ fraud-mcp-server
    (MCP client)                                 :9000
    ┌──────────────────────────────────────────► http://fraud-mcp-server:9000 ─────┐
    │                                                                              │
    fraud-mcp-server ──────────────────────▶ qdrant
    (QDRANT_HOST)                              :6333
    ┌──────────────────────────────────────────► http://qdrant:6333 ───────────────┘


                         CONFIG INJECTION
                         ================

    fraud-detection-config (ConfigMap) ──► fraud-agent-service Pod
                                       ──► fraud-mcp-server Pod
                                       ──► qdrant Pod

    fraud-detection-secrets (Secret)   ──► fraud-agent-service Pod
                                       ──► fraud-mcp-server Pod
```

---

## Traffic Flow Walkthrough

### 1. Internal Service Communication (ClusterIP DNS)

Services resolve each other by **Kubernetes DNS names** (ClusterIP):

```
fraud-agent-service ───→ fraud-ml-api:3000      (ML predictions)
                    └──→ fraud-mcp-server:9000    (RAG document retrieval)
fraud-mcp-server   ───→ qdrant:6333              (Vector DB queries)
```

> **How this works:** Each `ClusterIP` Service gets a DNS entry `<service-name>.<namespace>.svc.cluster.local`. Pods resolve these names to the Service's virtual IP, which load-balances to healthy pods.

### 2. External Access via Ingress (Not NodePort)

The **Ingress Controller** is the single entry point:

```
User ──→ fraud-detection.local/investigate ──→ Ingress ──→ fraud-agent-service (ClusterIP) ──→ Pod
```

Path routing rules:
| URL Path | Backend Service | Path After Rewrite |
|---|---|---|
| `/investigate` | `fraud-agent-service:8000` | `/` |
| `/health` | `fraud-agent-service:8000` | `/` |
| `/ml-api/predict` | `fraud-ml-api:3000` | `/predict` |
| `/mcp` | `fraud-mcp-server:9000` | `/` |
| `/qdrant` | `qdrant:6333` | `/` |

### 3. Cross-Node Traffic Routing via kube-proxy

Kubernetes automatically routes traffic across **different worker nodes** using `kube-proxy` — a networking agent that runs on every node. This is critical when pods are distributed across a multi-node cluster.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KUBERNETES CLUSTER                                  │
│                                                                             │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐      │
│  │     Worker Node 1            │    │     Worker Node 2            │      │
│  │                              │    │                              │      │
│  │  ┌────────────────────────┐  │    │  ┌────────────────────────┐  │      │
│  │  │ fraud-agent-service    │  │    │  │ fraud-ml-api           │  │      │
│  │  │ Pod                     │  │    │  │ Pod (Port 3000)        │  │      │
│  │  │ (Port 8000)             │  │    │  └────────────────────────┘  │      │
│  │  └────────────────────────┘  │    │                              │      │
│  │                              │    │  ┌────────────────────────┐  │      │
│  │  ┌────────────────────────┐  │    │  │ qdrant                 │  │      │
│  │  │ fraud-ml-api           │  │    │  │ Pod (Port 6333)        │  │      │
│  │  │ Pod (Port 3000)        │  │    │  └────────────────────────┘  │      │
│  │  └────────────────────────┘  │    │                              │      │
│  │                              │    │                              │      │
│  │  ┌────────────────────────┐  │    │  ┌────────────────────────┐  │      │
│  │  │ fraud-mcp-server       │  │    │  │ kube-proxy             │  │      │
│  │  │ Pod (Port 9000)        │  │    │  │ ─ iptables/IPVS rules  │  │      │
│  │  └────────────────────────┘  │    │  │ ─ knows ALL pod IPs    │  │      │
│  │                              │    │  │   on ALL nodes         │  │      │
│  │  ┌────────────────────────┐  │    │  └────────────────────────┘  │      │
│  │  │ kube-proxy             │  │    └──────────────────────────────┘      │
│  │  │ ─ iptables/IPVS rules  │  │                                          │
│  │  │ ─ knows ALL pod IPs    │  │                                          │
│  │  │   on ALL nodes         │  │                                          │
│  │  └────────────────────────┘  │                                          │
│  └──────────────────────────────┘                                          │
│                                                                             │
│                    ┌──────────────────────────────────┐                     │
│                    │  ClusterIP Service (Virtual IP)   │                     │
│                    │  fraud-ml-api:3000                │                     │
│                    │  DNS: fraud-ml-api                │                     │
│                    └──────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

**How cross-node routing works step-by-step:**

```
fraud-agent Pod          fraud-ml-api Service     fraud-ml-api Pod
(Node 1)                 (Virtual IP 10.96.x.x)   (Node 2)
    │                         │                        │
    │ 1. Calls               │                        │
    │ http://fraud-ml-api:3000                        │
    │────────────────────────►                        │
    │                         │                        │
    │                    2. kube-proxy intercepts      │
    │                       on Node 1 via iptables     │
    │                         │                        │
    │                    3. Routes to real pod IP      │
    │                       (Node 2, 10.0.x.x:3000)    │
    │                         │────────────────────────►
    │                         │                        │
    │◄────────────────────────│────────────────────────│
    │     4. Response         │       Response         │
    │      returned           │       returned         │
```

**Key facts about cross-node routing:**

| Concept | Explanation |
|---|---|
| **kube-proxy** | Runs as a DaemonSet on EVERY worker node. Creates iptables/IPVS rules that map Service virtual IPs to real pod IPs across all nodes. |
| **Cross-node routing** | A pod on Node 1 calling a Service can reach a pod on Node 2 — kube-proxy handles this transparently. |
| **No extra config** | Services work identically in single-node (Minikube) and multi-node clusters. No YAML changes needed. |
| **Load balancing** | If 2 replicas of `fraud-ml-api` exist (one on each node), kube-proxy round-robins traffic between them. |
| **Ingress is also cross-node** | The Ingress Controller (running on any node) can route to pods on any other node. |

**Why this matters for your setup:**

- Locally (Minikube): Single node — no cross-node routing needed, but the Service abstraction is still used
- In production (multi-node cluster): The same YAML files work unchanged — kube-proxy automatically handles routing across nodes
- Your application code never needs to know which node a pod lives on

---

## How to Expose `fraud-agent-service` to the Outside World?

> **Current approach: Ingress + ClusterIP** — This works in Minikube with `minikube addons enable ingress`.

Here are **all 3 options** for exposing fraud-detection-service externally:

### ❌ Option 1: NodePort (Not Recommended)

```yaml
# fraud-agent-service.yaml (modified)
spec:
  type: NodePort          # ❌ Change to NodePort
  ports:
    - port: 8000
      targetPort: 8000
      nodePort: 30080     # Optional: 30000-32767 range
```

| Pros | Cons |
|---|---|
| Simple, no extra controller needed | Port range limited (30000-32767) |
| Works without Ingress | Exposes node IP (not production-ready) |
| Good for quick testing | No path-based routing |
| | Node IP changes on restart |

Access: `http://$(minikube ip):30080/investigate`

### ✅ Option 2: ClusterIP + Ingress (Current — Recommended for Minikube)

```yaml
# fraud-agent-service.yaml (current — no change needed)
spec:
  type: ClusterIP          # ✅ Current setup
```

| Pros | Cons |
|---|---|
| Full URL routing (`/investigate`, `/health`) | Requires Ingress controller installed |
| Single entry point for all services | Slightly more complex setup |
| Path-based routing built-in | |
| Host-based virtual hosting | |
| TLS/SSL termination at Ingress | |

Access: `http://fraud-detection.local/investigate` (with `/etc/hosts` entry)

### 🔷 Option 3: LoadBalancer (Best for Cloud Production)

```yaml
# fraud-agent-service.yaml (modified for cloud)
spec:
  type: LoadBalancer       # 🔷 Change to LoadBalancer
  ports:
    - port: 8000
      targetPort: 8000
```

| Pros | Cons |
|---|---|
| Gets a real external IP address | Only works with cloud providers (AWS, GCP, Azure) |
| Load balancer handles TLS | Costs money (cloud LB charges) |
| Production best practice | No path-based routing (use with Ingress) |
| Works with `minikube tunnel` | |

Access: `http://<EXTERNAL-IP>:8000/investigate`

**For Minikube:** `minikube tunnel` creates a LoadBalancer IP locally.

---

## Summary — Answer to Original Questions

| Question | Answer |
|---|---|
| **Are services using NodePort or ClusterIP?** | **ClusterIP** — all 4 services use ClusterIP |
| **Is fraud-agent-service exposed externally?** | ✅ Yes — via **Ingress** (not directly via service type) |
| **Can it use NodePort?** | Yes, but Ingress is better — NodePort exposes raw node IPs |
| **Can it use LoadBalancer?** | Yes — use `minikube tunnel` locally, or on cloud it auto-provisions a cloud LB |
| **What is the recommended approach?** | **ClusterIP + Ingress** for local dev, **LoadBalancer + Ingress** for cloud prod |