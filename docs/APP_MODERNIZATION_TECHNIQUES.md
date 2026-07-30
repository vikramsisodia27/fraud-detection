# Application Modernization: Legacy to Microservices

> **Scope**: General-purpose modernization techniques, bottlenecks, and problem patterns.  
> **Not specific to fraud detection** — applies broadly to enterprise application modernization.

---

## Table of Contents

1. [Modernization Techniques](#1-modernization-techniques)
2. [Major Bottlenecks](#2-major-bottlenecks)
3. [Types of Problems](#3-types-of-problems)
4. [Decision Matrix — When to Use Which Technique](#4-decision-matrix)

---

## 1. Modernization Techniques

### 1.1 Strangler Fig Pattern

**Concept**: Incrementally replace legacy system functionality with new microservices, routing traffic to new vs. old via a proxy/API gateway. The legacy system is "strangled" over time.

```
┌──────────────┐      ┌──────────────┐
│   Client     │ ──►  │  API Gateway │
└──────────────┘      └──────┬───────┘
                             │
                  ┌──────────┴──────────┐
                  │                     │
           ┌──────▼──────┐      ┌──────▼──────┐
           │  Legacy     │      │  New Service │
           │  Monolith   │      │  (replacing  │
           │             │      │  a slice)    │
           └─────────────┘      └─────────────┘
```

| Pros | Cons |
|------|------|
| Low risk — incremental | Long transition period |
| Continuous delivery | Requires proxy/routing layer |
| Rollback-friendly | Both systems must coexist |

**When to use**: Large monolith with clear module boundaries; cannot afford a full rewrite.

---

### 1.2 Branch by Abstraction

**Concept**: Introduce an abstraction layer over the legacy code path, then swap the implementation underneath without changing callers.

1. Create an interface/abstract class for the functionality to modernize.
2. Implement the interface using the legacy code (existing behavior unchanged).
3. Develop a new microservice implementation behind the same interface.
4. Swap the implementation (feature flag / config toggle).
5. Remove the legacy code path.

| Pros | Cons |
|------|------|
| Zero downtime for consumers | Interface design must be correct |
| Reversible | May force abstraction that doesn't fit both impls |

**When to use**: When you need a clean API boundary before extracting to a service.

---

### 1.3 Feature Toggle / Flag-Driven Migration

**Concept**: Use feature flags to route specific users, tenants, or traffic to the new microservice. Enables gradual rollout and A/B testing.

| Technique | Granularity | Complexity |
|-----------|-------------|------------|
| Boolean toggle | On/off for all | Low |
| Percentage rollout | % of traffic | Medium |
| User/tenant-based | Specific cohorts | Medium |
| Context-based | Request attributes | High |

**When to use**: Multi-tenant systems, canary releases, risk-sensitive migrations.

---

### 1.4 Database Decomposition (Split the Data Layer)

Break the monolith's single database into domain-bound databases (Database per Service pattern).

```
Legacy:  Single DB ─── accounts, orders, inventory, users all in one schema

Target:  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
         │ Account │   │ Order   │   │ Inventory│   │ User    │
         │ Service │   │ Service │   │ Service │   │ Service │
         │   DB    │   │   DB    │   │   DB    │   │   DB    │
         └─────────┘   └─────────┘   └─────────┘   └─────────┘
```

| Challenge | Solution |
|-----------|----------|
| Cross-domain queries | CQRS + Materialized Views, API composition |
| Transactional integrity across services | Saga pattern (choreography or orchestration) |
| Data duplication | Event-driven sync (CDC — Change Data Capture) |
| Foreign key loss | Application-level referential integrity |

**When to use**: When the monolith's database is the primary coupling point (it often is).

---

### 1.5 Event-Driven Decomposition

**Concept**: Decouple services via asynchronous events (message broker: Kafka, RabbitMQ, NATS).

```
Monolith writes ──► Publish "OrderPlaced" event ──► Inventory Service subscribes
                                                     ► Notification Service subscribes
                                                     ► Billing Service subscribes
```

| Pros | Cons |
|------|------|
| Loose coupling | Eventual consistency |
| Scalable independently | Debugging harder (async flow) |
| Resilient (broker buffers) | Schema evolution complexity |

**When to use**: High volumes, multiple downstream consumers, need for decoupling.

---

### 1.6 Anti-Corruption Layer (ACL)

**Concept**: Place a translation layer between new microservices and the legacy system to protect the new domain model from legacy concepts.

```
New Service ──► ACL ──► Legacy System
                │
                └── Translates: legacy "BLNG_GRP_CD" → "billingGroupCode"
```

| Pros | Cons |
|------|------|
| Protects new domain model | Extra latency per call |
| Smooth coexistence | Additional code to maintain |
| Can be retired when legacy dies | Over-engineering risk if legacy dies fast |

**When to use**: Legacy system has a poorly designed or non-standard API that you cannot change.

---

### 1.7 Service Template / Strangler + Scaffold

**Concept**: Create a standardized microservice template (boilerplate: logging, health checks, metrics, CI/CD, Dockerfile, K8s manifests) so each extracted service is consistent.

| Component in Template | Purpose |
|-----------------------|---------|
| Health check endpoint | K8s liveness/readiness probes |
| Structured logging | Correlation IDs across services |
| Metrics endpoint | Prometheus scraping |
| Docker multi-stage build | Small image size |
| Helm chart / K8s manifests | Consistent deployment |
| CI/CD pipeline stub | Build, test, deploy |
| API docs (OpenAPI/gRPC proto) | Contract-first development |

**When to use**: Any project extracting more than 2–3 services.

---

### 1.8 gRPC / Contract-First Migration

**Concept**: Define service contracts (protobuf) before implementation. Both old and new code implement the same contract.

```protobuf
service OrderService {
  rpc GetOrder (GetOrderRequest) returns (Order);
  rpc CreateOrder (CreateOrderRequest) returns (Order);
}
```

| Pros | Cons |
|------|------|
| Language-agnostic | Learning curve for protobuf |
| Strong typing | HTTP/2 required |
| Code generation | Not all browsers support gRPC-web easily |

**When to use**: Polyglot environments, performance-sensitive paths.

---

## 2. Major Bottlenecks

### 2.1 Database Coupling (The #1 Bottleneck)

| Problem | Impact |
|---------|--------|
| Shared schema across domains | Cannot decompose independently |
| Stored procedures with business logic | Logic is hidden, hard to extract |
| Cross-table JOINs in monolith | Need API composition or CQRS after split |
| Single connection pool | Contention across services |

**Mitigation**:
1. Identify bounded contexts via Domain-Driven Design (DDD).
2. Use Database Views as read-only facades during transition.
3. Implement Change Data Capture (CDC) to sync data.

---

### 2.2 Transactional Integrity Across Services

| Problem | Impact |
|---------|--------|
| Distributed transactions (2PC) are impractical | Need Sagas instead |
| Compensating transactions are hard to write | Data inconsistency risk |
| No rollback across async events | Partial failures |

**Mitigation**:
1. Adopt Saga pattern (orchestration or choreography).
2. Design idempotent operations.
3. Accept eventual consistency where business allows.

---

### 2.3 Monolithic Deployment Cycle

| Problem | Impact |
|---------|--------|
| One deploy = full regression test | Slow release cadence (weeks → months) |
| Unrelated changes block each other | Team coordination overhead |
| Cannot scale parts independently | Over-provision or under-provision |

**Mitigation**:
1. Start with CI/CD for the monolith before decomposing.
2. Extract high-change-frequency services first.

---

### 2.4 Network / Latency

| Problem | Impact |
|---------|--------|
| In-memory call → network call (10μs → 1–10ms) | Perceived slowdown |
| Chatty service-to-service calls | Cascading latency |
| N+1 problem across services | Degraded UX |

**Mitigation**:
1. Batch requests (GraphQL, gRPC streaming).
2. Add caching (Redis, CDN, local caches).
3. Use asynchronous vs synchronous communication where possible.

---

### 2.5 Observability Gap

| Problem | Impact |
|---------|--------|
| Monolith: one log file, one app metric | Simple |
| Microservices: 10+ log streams, distributed traces | Complex debugging |

**Mitigation**:
1. Mandate correlation IDs across services.
2. Deploy centralized logging (ELK/Loki) + tracing (Jaeger/Tempo) + metrics (Prometheus/Grafana).
3. Implement health check + readiness + liveness endpoints from Day 1.

---

### 2.6 Configuration / Secrets Sprawl

| Problem | Impact |
|---------|--------|
| Each service needs DB creds, API keys | Secret explosion |
| Environment-specific configs | Drift between dev/staging/prod |
| Hardcoded endpoints | Brittle, breaks on redeploy |

**Mitigation**:
1. Centralized config server (Consul, Kubernetes ConfigMaps/Secrets, Vault).
2. Externalize all config — 12-Factor App methodology.

---

### 2.7 Testing Complexity

| Problem | Impact |
|---------|--------|
| Unit tests alone insufficient | Must test inter-service contracts |
| End-to-end tests are slow/fragile | Long feedback loops |
| No test doubles for external services | Flaky tests |

**Mitigation**:
1. Use Consumer-Driven Contract Tests (Pact, Spring Cloud Contract).
2. Mock/stub external services in integration tests.
3. Test harnesses in CI with service virtualization.

---

## 3. Types of Problems

### 3.1 Architectural Problems

| Problem | Description | Example |
|---------|-------------|---------|
| **Big Ball of Mud** | No clear boundaries, every module depends on every other | `UserService.ImportAll()` called from 15 modules |
| **God Class / Service** | Single class/service does everything | `OrderManager` handles validation, pricing, inventory, shipping |
| **Shared Persistence** | Multiple modules read/write same tables | `orders` table updated by 4 different modules directly |
| **Circular Dependencies** | Service A calls B, B calls C, C calls A | Monolith startup fails due to circular bean wiring |
| **No API Contract** | REST endpoints defined by implementation, not contract | Breaking changes go undetected until production |

### 3.2 Organizational Problems

| Problem | Description | Microservice Solution |
|---------|-------------|----------------------|
| **Conway's Law violation** | Team structure doesn't match architecture | Align teams to bounded contexts |
| **Ownership ambiguity** | "Who owns this code?" | Each service owned by exactly one team |
| **Knowledge silos** | Only 1 person understands module X | Service extraction forces documentation |
| **Release coordination** | Every release needs 5 teams to sign off | Independent deployability reduces coordination |

### 3.3 Data Problems

| Problem | Description | Impact |
|---------|-------------|--------|
| **Data silos** | No single source of truth | Reconciliation nightmares |
| **Schema coupling** | Changing one table breaks 10 services | Slow iteration |
| **Reporting needs** | BI reports need data from 5 service DBs | Requires data warehouse / CDC pipeline |
| **Data migration** | Moving 500GB to new service DB | Downtime, sync issues, rollback complexity |

### 3.4 Operational Problems

| Problem | Description |
|---------|-------------|
| **Startup / Shutdown Order** | Service A depends on Service B being up first |
| **Versioning** | Deploying v2 of Service A breaks v1 of Service B |
| **Retry Storms** | All services retry simultaneously during outage |
| **Cascade Failures** | One slow service causes all upstream services to time out |
| **Configuration Drift** | Staging works, production doesn't (different config/versions) |
| **Orphaned Services** | No one knows who owns the `reporting-service` deployed 3 years ago |

### 3.5 Security Problems

| Problem | Description |
|---------|-------------|
| **East-West traffic** | No encryption between services (service mesh solves this) |
| **Credential explosion** | 100 services × 3 environments = 300 DB passwords to manage |
| **Token propagation** | User JWT must flow through 5 services for audit |
| **Perimeter dissolved** | Old firewall approach doesn't work — need zero-trust |

### 3.6 Migration Anti-Patterns

| Anti-Pattern | Description | Why It Fails |
|--------------|-------------|-------------|
| **Big Bang Rewrite** | Rewrite the entire monolith as microservices in one go | Takes too long, business needs change, never ships |
| **Distributed Monolith** | Microservices deployed separately but tightly coupled via shared DB | Worst of both worlds — complexity of distribution + inflexibility of monolith |
| **Over-splitting** | Each method becomes a service | Network overhead, debugging nightmare |
| **No API Versioning** | `/api/v1/users` → change → no version bump | Breaks existing clients |
| **Copy-Paste Service Creation** | Manually copying code for each new service | Inconsistency, security gaps, maintenance burden |

---

## 4. Why Domain-Driven Design (DDD) is Used

### 4.1 The Core Problem DDD Solves

The hardest question in modernization: **"Where do I draw the boundaries between services?"**

Without DDD, teams typically:

| Wrong Approach | Result |
|----------------|--------|
| Split by technical layer (frontend/backend/DB) | Not microservices — just distributed layered architecture |
| Split by UI page | Massive duplication, cross-service dependencies |
| Split arbitrarily | **Distributed Monolith** — services deployed independently but still tightly coupled via shared database |

### 4.2 DDD Concepts That Matter for Modernization

| Concept | Meaning | Why It Helps Service Extraction |
|---------|---------|---------------------------------|
| **Bounded Context** | A logical boundary where a specific model has a specific meaning | Tells you exactly which code + data belong together in one service |
| **Ubiquitous Language** | Same terminology used by business + developers | Ensures API contracts match business concepts, not technical artifacts |
| **Aggregate** | A cluster of objects that must be transactionally consistent | Maps naturally to a service's data ownership boundary |
| **Domain Event** | Something that happened that other parts care about | Defines async communication contracts between services |

**Example**: "Customer" means different things in different contexts:
- **Orders context**: Customer = person who places an order (name, address, email)
- **Shipping context**: Customer = physical delivery address + delivery preferences
- **Billing context**: Customer = credit profile + payment method

DDD makes these distinctions explicit so you don't build one "Customer" service that tries to satisfy all three (which leads to a distributed monolith).

### 4.3 Why DDD is the Foundation of Modernization

| Without DDD | With DDD |
|-------------|----------|
| Services share a single database | Each service owns its data |
| Changing one service breaks others | Bounded contexts are autonomous — changes stay local |
| "We need a distributed transaction across 5 services" | Cross-service transactions are rare (aggregates define consistency boundaries) |
| Every service has a bloated "Customer" model | Each context has its own simplified Customer model |
| API breaks every week | Contracts are stable — they match business concepts |

### 4.4 When DDD is Overkill

- Simple CRUD apps (5 tables, no complex business logic)
- Team of 2 developers (modular monolith is sufficient)
- Prototypes / MVPs (refactor toward DDD later)

---

## 5. How to Decide What to Extract First — Scoring Method

### 5.1 The Selection Framework

Don't guess. Score each module on 4 axes (1-10):

| Criterion | Question | Weight |
|-----------|----------|--------|
| **Business Value** | How much does this module contribute to revenue/operations? | High |
| **Pain Level** | Is this module slow, fragile, causing incidents? | High |
| **Dependency Count** | How many other modules does it call? (Lower = easier) | Medium |
| **Data Isolation** | Can its data be separated into its own database? | Medium |

### 5.2 Worked Example: Insurance Claims System

| Module | Business Value | Pain | Dependencies (inverse) | Data Isolation | **Total** |
|--------|---------------|------|----------------------|----------------|-----------|
| **Fraud Detection** | 10 | 9 | 8 (few deps) | 8 (read-only) | **35 ← START HERE** |
| Claims Filing | 10 | 8 | 6 | 6 | 30 |
| Payout Processing | 9 | 7 | 5 | 5 | 26 |
| Policy Management | 8 | 3 | 9 | 9 | 29 |
| Document Management | 4 | 2 | 10 | 8 | 24 |

**Decision**: Fraud Detection wins — highest pain + high business value + few dependencies + read-only data (easy to split).

**Key rule**: Biggest ≠ Best. A huge module with tight coupling is a worse first target than a smaller, painful, isolated module.

---

## 6. Service Extraction Phase (Phase 3) — Step by Step

This is the actual process of pulling one module out of the monolith into a standalone service.

### 6.0 Prerequisites

Before starting Phase 3, the monolith should already be:
- Running on a modern framework (e.g., Spring Boot, not a legacy app server)
- Organized into Gradle sub-modules or clean package boundaries
- Config externalized (no hardcoded endpoints, credentials, etc.)

### 6.1 Step 1: Audit Dependencies

For every call the target module makes, classify it:

| Type | Meaning | Action |
|------|---------|--------|
| **Inbound** | Other modules call this module | These become API consumers of the new service |
| **Outbound (data)** | Target module reads/writes shared DB tables | Must become API calls to the owning service |
| **Outbound (function)** | Target module calls another module's method | Must become network calls or async events |
| **Moving with target** | Code that only the target module uses | Copied entirely into the new service |

**If the target module writes to tables that other modules also write to**, you cannot extract cleanly until you untangle data ownership first.

### 6.2 Step 2: Introduce an Anti-Corruption Layer (ACL)

Wrap all outgoing calls from the target module behind interfaces. This achieves three things:

1. **Compile-time independence**: Target module no longer imports other monolith modules — only interfaces
2. **Drop-in ready**: Same module code can be copied to a new project; only the implementations change (in-process → network)
3. **Testability**: Target module can be tested in isolation with mock implementations

**Validation gate**: Run an architecture test that verifies the target module has zero import dependencies on other monolith packages. If any exist, the ACL is incomplete.

### 6.3 Step 3: Copy to a New Project

Create a brand new project containing:
- The target module's business logic, domain models, repositories
- New client implementations (these make HTTP calls to the monolith instead of calling code directly)
- Infrastructure: health endpoints, Dockerfile, configuration, CI/CD pipeline

**What changes conceptually**:
- **Direct calls → network calls**: Method invocations become HTTP requests or message publications
- **Direct DB access → API calls**: Shared table reads become API calls to the data owner
- **Synchronous → asynchronous**: Non-critical side effects use events instead of blocking calls

### 6.4 Step 4: Deploy Both Versions (Strangler Fig) with Feature Flag

The API Gateway routes traffic based on a feature flag:

| Flag State | Traffic Routing |
|------------|-----------------|
| OFF | 100% → monolith (new service is deployed but silent) |
| ON (specific paths) | Fraud requests → new service; everything else → monolith |
| ON (full) | 100% → new service |

**Rollback is instant**: Flip the flag back to OFF and all traffic returns to the monolith.

### 6.5 Step 5: Gradual Cutover Timeline

| Stage | Traffic to New Service | Duration | Verification |
|-------|----------------------|----------|-------------|
| Internal | 0% (manual testing) | 1 week | All test cases pass |
| Canary | 5% | 1 week | Compare outputs — must match old results |
| Ramp-up | 25% → 50% | 2 weeks | Monitor latency, error rate, CPU |
| Full | 100% | 1 week | Old code disabled in monolith |
| Cleanup | 100% | 1 week | Old code deleted; feature flag removed |

### 6.6 Step 6: After Cutover — What Changes

| Aspect | Before (in monolith) | After (extracted service) |
|--------|---------------------|---------------------------|
| **Data ownership** | Shared DB reads/writes | Own database; reads via API |
| **Transactions** | Single DB transaction | Saga pattern (compensating actions) |
| **Latency** | Sub-millisecond (same JVM) | Network latency added (caching mitigates) |
| **Resilience** | In-process exception handling | Circuit breakers, timeouts, retries needed |
| **Deployment** | One monolith deployed | Service deploys independently |
| **Scaling** | Entire monolith scales together | Service scales independently |

### 6.7 Common Pitfalls in Phase 3

| Pitfall | What Happens | How to Avoid |
|---------|-------------|--------------|
| **Distributed transaction failure** | Service saves, but can't notify monolith | Use Saga: save → publish event → monolith consumes. On failure, publish compensation event |
| **High latency** | What was instant (in-memory) now takes 10-100ms (network) | Add caching for reads; async for non-critical ops |
| **Tight data coupling discovered late** | Two modules share 50 tables | Split data ownership first: migrate via CDC + dual-write phase |
| **N+1 API calls** | New service calls monolith once per row in a loop | Add batch endpoints to fetch many records in one call |

---

## 7. Tool & Platform Upgrades

### 7.1 Maven → Gradle (Build Tool Migration)

**Why upgrade**:

| Benefit | Impact |
|---------|--------|
| Faster incremental builds (daemon + build cache) | Developer feedback 2-5x faster |
| Better multi-module support | Essential for modular monolith → microservices |
| Kotlin DSL | Type-safe, IDE-friendly build scripts |
| Task-based (not lifecycle-based) | More flexible build pipelines |

**Migration approaches**:

| Approach | Effort | Risk | Best For |
|----------|--------|------|----------|
| **Parallel build** (both Gradle + Maven coexist) | Medium | Low | Large teams, complex builds |
| **Big bang switch** | Low | Medium | Small projects, simple builds |
| **Per-module migration** | High | Low | Multi-module projects |

**Recommended approach — Parallel Build**:

1. Generate Gradle build from existing POM
2. Fix discrepancies: custom plugins, profiles, dependency scopes
3. Run both `mvn clean test` AND `gradle test` — outputs must match
4. Tune performance: enable daemon, parallel execution, build cache
5. Remove Maven files only after all developers have validated

**Critical rule**: Never change build tool AND application server at the same time. Change only one variable at a time.

### 7.2 WAS (WebSphere Application Server) → Spring Boot

**Why migrate**:

| WAS (Legacy) | Spring Boot (Target) |
|-------------|---------------------|
| EAR/WAR deployment | Fat JAR (embedded server) |
| JNDI lookups for everything | Auto-configuration + properties files |
| EJB (Stateless, Stateful) | Spring annotations |
| JMS Message-Driven Beans | Message listener annotations |
| JAAS + WAS security roles | Spring Security + OAuth2/JWT |
| Container-managed transactions | Declarative `@Transactional` |
| WAS admin console for datasources | `application.yml` |
| Heavy server startup (minutes) | Fast startup (seconds) |
| Expensive license costs | Open source |

**Migration phases**:

```
Phase 1: Lift & Shift (WAS code → Spring Boot, minimal changes)
├── Goal: Get same code running on embedded Tomcat
├── No business logic changes
├── Replace: JNDI lookups → config properties
├── Replace: web.xml → annotation-based config
├── Replace: EJB injection → Spring annotation injection
└── Result: Monolith runs as Spring Boot fat JAR

Phase 2: Modularize (still a monolith, but organized)
├── Extract packages into sub-modules
├── Define boundary rules (ArchUnit tests)
├── Replace EJB local interfaces with Spring interfaces
└── Result: Modular monolith — clean boundaries, single deployable

Phase 3: Extract First Service (see Section 6 above)
├── Pick one module
├── Build ACL interfaces
├── Deploy as separate service with feature flag
└── Result: 1 microservice + modular monolith

Phase 4: Containerize + Orchestrate
├── Dockerfile with multi-stage build
├── Health checks, metrics endpoints
├── Kubernetes manifests (Deployment, Service, ConfigMap, Secret)
└── Result: Runs on Kubernetes
```

**Testing during WAS → Spring Boot migration**:

| Test Type | What It Validates |
|-----------|-------------------|
| Smoke test | Application starts and serves requests |
| Feature parity | 100 identical inputs → 100 identical outputs |
| Performance | No regression worse than 5% from WAS baseline |
| Transactional | Same rollback behavior as container-managed transactions |
| Integration | JMS, DB, batch jobs all still work |

### 7.3 Decision Framework for Tool Upgrades

| Question | If Yes → | If No → |
|----------|----------|---------|
| Is the current tool causing active pain? (slow builds, expensive license, nearing end-of-life) | **Do it now** | Defer |
| Is the org undergoing a concurrent architecture change? | **Defer tool upgrade** — too much change at once | **Do it now** |
| Is the team familiar with the target technology? | **Do it** | Add training buffer (2-4 weeks) |
| Does the vendor still support the old platform? | Wait until support ends | Do it before support ends |

---

## 8. Simple Explanation — The Restaurant Analogy

Think of a legacy monolith like a **single restaurant** where everything happens in one kitchen:

- One chef cooks everything (one application server)
- One pantry serves all dishes (one shared database)
- If the fryer breaks, the whole restaurant can't serve food (one failure = everything down)
- To add a new dish, retrain every chef (big, risky deployments)

You want to modernize into a **food court** with separate stalls (microservices), each with its own kitchen and menu.

**The problem**: You can't close the restaurant for 6 months. Customers are eating right now. You must remodel **while serving food**.

### 8.1 Step-by-Step in Restaurant Terms

**Step 1: Pick a dish to move first**
- Which dish gets the most complaints? (highest pain)
- Which dish makes the most money? (highest value)
- Which dish uses ingredients no other dish uses? (most isolated)

**Step 2: Draw a box around it**
- List every ingredient the dish touches
- Decide: moves with dish, stays in main kitchen, or needs a new communication method
- The recipe must no longer depend on anything in the main kitchen — it only has phone numbers to call for shared ingredients

**Step 3: Build a new stall (but don't open yet)**
- Separate kitchen, separate pantry, separate phone (API)
- One phone operator calls the main kitchen for shared ingredients
- The old kitchen still has the same recipe — both can make the dish

**Step 4: Open gradually**
- Week 1: Only staff eat from the new stall
- Week 2: 5% of customers sent to new stall
- Week 3: 25%
- Week 4: 100%
- **Safety net**: If the new stall burns a dish, flip a switch — all customers go back to the main kitchen instantly

**Step 5: Clean up**
- Remove the old recipe from the main kitchen
- Reclaim that kitchen space
- Pick the next dish to extract

### 8.2 The Most Important Rule

| Wrong Approach | Right Approach |
|----------------|----------------|
| Change everything at once | Change ONE thing at a time |
| Rewrite the entire menu from scratch | Move one dish at a time |
| Throw away the old kitchen first | Build the new kitchen next to the old one |
| Combine platform upgrade + architecture change | Keep them in separate phases |

**One variable at a time**: If Phase 1 is "move from WAS to Spring Boot," then Phase 2 is "modularize the code," and Phase 3 is "extract first service." Never combine phases.

---

## 9. Decision Matrix — When to Use Which Technique

| Scenario | Recommended Technique(s) | Avoid |
|----------|------------------------|-------|
| Large legacy, no downtime allowed | Strangler Fig + Feature Toggle | Big Bang Rewrite |
| Single DB with cross-module queries | Database Decomposition + CQRS | Premature service split |
| Performance-sensitive path | gRPC + Branch by Abstraction | REST-over-HTTP/1.1 |
| Multi-tenant SaaS migration | Tenant-based Feature Flag | Hard cutover |
| Poor legacy API (cannot change) | Anti-Corruption Layer | Direct integration |
| < 5 services total | Strangler Fig is overkill — consider modular monolith first | Full microservice tooling |
| High-throughput event processing | Event-Driven Decomposition | Request-response for everything |
| Team of 3 developers | Modular monolith, extract only when needed | Kubernetes + 10 microservices |
| Zero trust security required | Service Mesh (Istio/Linkerd) + mTLS | Perimeter firewall |
| WAS → Spring Boot migration | Lift & Shift first, then modularize, then extract | Doing architecture + platform change simultaneously |
| Maven → Gradle migration | Parallel build (both coexist during transition) | Big bang switch without overlap period |

---

## Summary Checklist for a Modernization Project

- [ ] Run Event Storming workshops to identify bounded contexts (DDD)
- [ ] Score modules: business value + pain level + dependency count + data isolation
- [ ] Pick the highest-scoring module as the first extraction target
- [ ] Audit all dependencies of the target module (inbound, outbound, shared data)
- [ ] Build Anti-Corruption Layer interfaces in the monolith
- [ ] Validate with architecture tests (zero illegal dependencies)
- [ ] Create new service project with its own database
- [ ] Deploy service alongside monolith (silent, no traffic)
- [ ] Route traffic via feature flag (5% → 25% → 50% → 100%)
- [ ] Add observability (logs, traces, metrics) on Day 1
- [ ] Enforce API contracts (OpenAPI / protobuf)
- [ ] Build CI/CD for each service independently
- [ ] Implement Saga pattern for cross-service transactions
- [ ] Retire legacy code path once 100% traffic is migrated
- [ ] Repeat for the next module
- [ ] For tool upgrades (Maven→Gradle, WAS→Spring Boot): change only one variable at a time
- [ ] Never combine platform upgrade with architecture change in the same phase

---

