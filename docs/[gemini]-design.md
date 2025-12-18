# Soulcaster Production Design Doc

## 1. Executive Summary

Soulcaster is a self-healing development loop system. Currently, it exists as a "Hackathon MVP" with a split architecture between a Python backend and a Next.js full-stack application. To productionize this for a Product Hunt launch, we need to unify the business logic, secure the system, and improve reliability.

## 2. Current Architecture (The "Hackathon" State)

The current system consists of three loosely coupled components sharing a Redis database.

### 2.1 Components

1.  **Python Backend (`backend/`)**
    -   **Role**: Ingestion & Simple Management.
    -   **Tech**: FastAPI, PRAW (Reddit), Redis.
    -   **Function**: Polls Reddit, receives Sentry webhooks, stores raw feedback in Redis. Performs "naive" clustering (group by source/subreddit).
    -   **Issues**: Does not perform the advanced vector clustering. No authentication.

2.  **Dashboard (`dashboard/`)**
    -   **Role**: UI & The "Real" Brain.
    -   **Tech**: Next.js (App Router), Tailwind, Upstash Vector, AWS SDK.
    -   **Function**:
        -   Reads directly from Redis (bypassing Backend API).
        -   Implements **Vector Clustering** (via `/api/clusters/run-vector`) using Upstash Vector and Google GenAI.
        -   Triggers the Coding Agent by directly launching AWS Fargate tasks.
    -   **Issues**: "Split Brain" logic (clustering here vs backend). Direct DB access couples frontend to data schema. Direct AWS calls require high-privilege credentials in the frontend server.

3.  **Coding Agent (`coding-agent/`)**
    -   **Role**: The Worker.
    -   **Tech**: Python, `kilocode` CLI, GitHub CLI.
    -   **Function**: Standalone script that clones a repo, uses AI to fix an issue, and opens a PR.
    -   **Issues**: Currently triggered as a one-off container task. No robust queueing or retry mechanism.

### 2.2 Data Flow (Current)

1.  **Ingestion**: `Python Backend` -> `Redis` (Raw Feedback).
2.  **Clustering**: `Next.js API` (Triggered manually?) -> `Redis` (Clusters).
3.  **View**: `Next.js UI` -> `Redis` (Direct Read).
4.  **Fix**: `Next.js UI` -> `AWS Fargate API` -> `Coding Agent Container`.

## 3. Critical Issues & Risks

1.  **Split Brain Clustering**: Logic exists in both Python and TypeScript. The "smart" vector clustering is in Next.js, while the "ingestion" clustering is in Python. This leads to inconsistent states and hard-to-maintain code.
2.  **Security**:
    -   Backend endpoints are public (no auth).
    -   Dashboard has direct access to AWS credentials to launch tasks.
3.  **Scalability**:
    -   Direct Fargate launch is synchronous-ish and hits AWS rate limits/quotas easily.
    -   No message queue for high-volume ingestion or agent jobs.
4.  **Coupling**: Dashboard knows too much about the database schema.

## 4. Proposed Architecture (Production/Launch Ready)

We will move towards a **Unified Backend** architecture. The Python service should become the single source of truth for logic, data, and orchestration.

### 4.1 Architecture Diagram

```mermaid
graph TD
    User[User / Webhook] --> |Ingest| API[Python Backend API]
    UI[Next.js Dashboard] --> |View/Action| API
    
    subgraph "Backend Core (FastAPI)"
        API --> |Read/Write| DB[(Redis / Upstash)]
        API --> |Vector Search| Vector[(Upstash Vector)]
        API --> |Enqueue| Queue[Job Queue (Redis Stream)]
    end
    
    subgraph "Worker Layer"
        Worker[Python Worker] --> |Poll| Queue
        Worker --> |Run| Agent[Coding Agent Logic]
    end
    
    Agent --> |Open PR| GitHub[GitHub API]
```

### 4.2 Key Decisions

#### Decision 1: Unify Logic in Python Backend
-   **Why**: Python is better suited for AI/ML tasks (LlamaIndex, LangChain, etc.) and is already handling ingestion.
-   **Action**: Port `dashboard/lib/vector.ts` and `clustering.ts` logic to the Python backend.
-   **Benefit**: Single "Brain". Dashboard becomes a dumb UI.

#### Decision 2: API-First Dashboard
-   **Why**: Decouples frontend to DB schema. Allows backend to evolve independently.
-   **Action**: Update Dashboard to fetch data from `http://backend/api/...` instead of `lib/redis.ts`.
-   **Benefit**: Better security, cleaner separation of concerns.

#### Decision 3: Async Job Queue for Agents
-   **Why**: Direct Fargate launch is brittle.
-   **Action**:
    -   Use Redis Streams (already have Redis) or a simple task queue (e.g., ARQ or Celery).
    -   Backend enqueues a "Fix Job".
    -   A long-running Worker process (or a scaled Fargate service) picks up jobs and runs the `coding-agent` logic.
-   **Benefit**: Retries, rate limiting, better observability.

#### Decision 4: Authentication
-   **Why**: Public endpoints are dangerous.
-   **Action**: Implement API Key auth for webhooks and Session/JWT auth for Dashboard access (via NextAuth -> Backend validation).

## 5. Implementation Roadmap

### Phase 1: Consolidation (The "Brain Transplant")
-   [ ] Port Vector Clustering logic from TS to Python.
-   [ ] Expose `POST /clusters/rebalance` endpoint on Backend.
-   [ ] Update Dashboard to call Backend for clustering.

### Phase 2: Decoupling (The "Lobotomy")
-   [ ] Create Backend endpoints for all Dashboard views (`GET /clusters`, `GET /jobs`).
-   [ ] Refactor Dashboard to use API calls instead of direct Redis access.
-   [ ] Remove AWS SDK from Dashboard.

### Phase 3: Reliability (The "Nervous System")
-   [ ] Implement a simple Redis-based job queue in Python.
-   [ ] Refactor `coding-agent` to run as a worker consuming this queue.
-   [ ] Add basic API Key authentication.

## 6. Open Questions
-   **Hosting**: Are we keeping the "Serverless" vibe (Vercel + Upstash)? If so, the "Long running worker" needs a home (e.g., Railway, Fly.io, or AWS Fargate Service).
-   **Vector DB**: Stick with Upstash Vector? (Yes, it's easy and works with the stack).
