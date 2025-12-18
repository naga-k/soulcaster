# Soulcaster Production Design — Claude's Take

## TL;DR

You have a working system with smart clustering and autonomous code fixes. The architecture is sound for a side project. Don't over-engineer—focus on: **auth (1 day), error visibility (1 day), and one reliability fix (1 day)**. Ship to ProductHunt, then iterate based on real usage.

---

## Current State: What You Actually Have

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Reddit/Sentry  │────▶│  FastAPI Backend │────▶│  Upstash Redis  │
│    (Sources)    │     │  (Ingestion)     │     │  (Data Store)   │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
┌─────────────────┐     ┌──────────────────┐              │
│   Next.js UI    │────▶│  Vector Cluster  │◀─────────────┘
│   (Dashboard)   │     │  (Gemini + UVec) │              │
└────────┬────────┘     └──────────────────┘              │
         │                                                 │
         │              ┌──────────────────┐              │
         └─────────────▶│  Fargate Agent   │◀─────────────┘
                        │  (Kilo → GitHub) │
                        └──────────────────┘
```

### What Works Well
- **Vector clustering is sophisticated**: 0.72 threshold, cohesion scores, batch processing
- **Agent actually ships PRs**: Full flow from issue to PR works
- **Infrastructure is serverless-friendly**: Upstash + Fargate = low fixed costs
- **Code is testable**: Good separation, pure functions for clustering logic

### What's Missing (But Manageable)
| Gap | Severity | Effort to Fix |
|-----|----------|---------------|
| No authentication | High | 2-4 hours |
| Print-based logging | Medium | 2 hours |
| Silent Redis fallback | Medium | 1 hour |
| No webhook verification | Medium | 1 hour |
| No rate limiting | Low | 1 hour |

---

## Decision Points

### 1. Architecture: Unify vs Keep Split?

**Gemini says**: Port everything to Python, make Dashboard dumb.
**ChatGPT says**: Route through FastAPI, keep clustering in a worker.
**My take**: **Keep the split for now.**

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **A: Keep Split** | Ship faster, TypeScript clustering works, Next.js ecosystem | Two languages, some duplication | **Do this for launch** |
| **B: Unify to Python** | Single brain, better for ML | Rewrite clustering, delay launch | Do post-traction |

**Rationale**: Your TypeScript vector clustering is working and tested. Porting it to Python buys you architectural purity but delays launch by 1-2 weeks. The "split brain" risk is manageable—just make Dashboard the authoritative source for clustering (it already is).

**Quick fix**: Remove the naive Python auto-clustering from `_auto_cluster_feedback()`. Let Dashboard handle all clustering via `/api/clusters/run-vector`. This eliminates split-brain with a 10-line change.

---

### 2. Authentication: What's Minimum Viable?

| Option | Complexity | Security | Best For |
|--------|------------|----------|----------|
| **A: API Key header** | Low | Medium | Webhooks, internal APIs |
| **B: NextAuth session → Backend** | Medium | Good | User-facing dashboard |
| **C: Full OAuth everywhere** | High | Best | Post-traction |

**Recommendation**: Do both A and B.

```
Webhooks (Sentry, manual ingest) → API Key in header
Dashboard users → NextAuth (already set up) → pass token to backend
Agent callbacks → API Key
```

**Implementation** (2-4 hours):
1. Add `X-API-Key` header check to FastAPI middleware
2. Pass NextAuth session token to backend on Dashboard API calls
3. Backend validates: API key OR valid session token
4. Store API keys in environment variables (not a database)

---

### 3. Error Handling: What Breaks Silently?

Current failure modes that lose data or confuse users:

| Failure | Current Behavior | Fix |
|---------|------------------|-----|
| Redis unavailable | Silent fallback to in-memory, data lost on restart | Fail fast, return 503 |
| Embedding API fails | `embeddingFailures++`, item skipped | Retry 3x, then queue for later |
| Fargate task fails | Job stuck in "running" forever | Timeout + mark failed after 30m |
| Sentry webhook invalid | 500 error, no detail | Validate signature, return 400 |

**Quick wins** (1-2 hours each):
1. Remove in-memory fallback from production (`store.py:23`)—if Redis is down, the service is down
2. Add `/health` endpoint that checks Redis connection
3. Add job timeout: if status is "running" for >30 minutes, mark as "failed"

---

### 4. Observability: What Do You Need to Debug?

| Level | What | Tool | Priority |
|-------|------|------|----------|
| **Request tracing** | Correlate requests across services | Request ID header | High |
| **Structured logs** | Search/filter logs | JSON logging | High |
| **Metrics** | Cluster rate, API latency | Defer | Low |
| **Distributed tracing** | Full request waterfall | Defer | Low |

**Minimum viable** (2 hours):
1. Add `X-Request-ID` header (generate if missing)
2. Replace `print()` with structured logger: `{"timestamp", "level", "request_id", "message"}`
3. Use Vercel's built-in logging for Dashboard, CloudWatch for Fargate

Don't add Prometheus/Grafana/OpenTelemetry yet. You don't have enough traffic to need it.

---

### 5. LLM Provider: Gemini vs Others?

| Provider | Embedding Cost | Speed | Recommendation |
|----------|----------------|-------|----------------|
| Gemini `text-embedding-004` | Free tier generous | Fast | **Keep for embeddings** |
| Gemini `2.5-flash` | Cheap | Fast | **Keep for summaries** |
| OpenAI | $0.13/1M tokens | Fast | Unnecessary switch |
| Claude | More expensive | Quality | Use for agent reasoning if Kilo supports |

**Keep Gemini**. It's working, cheap, and the integration is done. Only switch if you hit rate limits or quality issues.

---

### 6. Queueing: Redis Streams vs SQS vs Nothing?

| Option | Pros | Cons |
|--------|------|------|
| **A: Nothing (current)** | Simple, fewer moving parts | No retry, no rate limiting |
| **B: Redis Streams** | Already have Redis, simple | Learning curve, manual retry logic |
| **C: SQS** | Battle-tested, built-in DLQ | Another AWS service, more config |

**Recommendation**: **Keep "nothing" for launch.**

Your current flow is: user clicks button → Fargate task starts → success or failure. This works. Adding a queue adds complexity for a problem you don't have yet (scale).

**When to add queueing**: If you're processing >100 items/day or need guaranteed delivery of agent jobs.

---

## Implementation Priority

### This Week (Pre-Launch)

| Task | Effort | Impact |
|------|--------|--------|
| 1. Add API key auth to backend | 2h | Blocks public abuse |
| 2. Remove in-memory store fallback | 30m | Prevents silent data loss |
| 3. Add `/health` endpoint | 30m | Enables monitoring |
| 4. Disable Python auto-clustering | 10m | Eliminates split-brain |
| 5. Add request ID logging | 1h | Enables debugging |

### Post-Launch (If Traction)

| Task | Trigger |
|------|---------|
| Port clustering to Python | Dashboard becomes bottleneck |
| Add Redis Streams queue | >100 jobs/day |
| Add Postgres for audit | Need historical analytics |
| Multi-tenant auth | Multiple users/orgs |

---

## Files to Modify

### Backend Auth (Highest Priority)
```
backend/main.py      → Add API key middleware
backend/store.py     → Remove in-memory fallback (lines 1-20)
```

### Eliminate Split-Brain
```
backend/main.py      → Remove _auto_cluster_feedback() call from ingest routes
```

### Health Checks
```
backend/main.py      → Add GET /health that pings Redis
dashboard/app/api/health/route.ts → Add health endpoint
```

### Logging
```
backend/main.py      → Replace print() with structlog
dashboard/lib/*.ts   → Add request ID to console.log calls
```

---

## What I'd Skip

- **Postgres**: Redis is fine for your data volume. Add it when you need complex queries or audit trails.
- **Kubernetes**: Fargate is simpler and cheaper at your scale.
- **OpenTelemetry**: Overkill. Structured logs + request IDs are enough.
- **API versioning**: You don't have external API consumers yet.
- **CI/CD gates**: Keep it simple—main branch deploys to production.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Redis data loss | Low (Upstash is reliable) | High | Enable Upstash backups ($) |
| Fargate task hangs | Medium | Low | Add 30m timeout to job status |
| LLM rate limits | Low | Medium | Add exponential backoff |
| Public API abuse | High (no auth) | Medium | **Add auth before launch** |
| Agent creates bad PRs | Medium | Low | Users review PRs anyway |

---

## Summary

**Don't let perfect be the enemy of shipped.**

Your architecture is fine for a ProductHunt launch. The "split brain" concern is real but manageable—just make Dashboard authoritative for clustering. The auth gap is the only blocker.

Spend 1-2 days on:
1. API key authentication
2. Remove silent failures
3. Add basic logging

Then ship it. You'll learn more from 10 real users than from another week of architecture.
