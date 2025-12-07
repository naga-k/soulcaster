# Database Design (Hackathon Redis Plan)

## Soulcaster Snapshot (Plan vs Reality)

Quick matrix; the sections below remain the original design details.

| Area          | Originally Planned                                            | Implemented in Soulcaster                                      | Extra / Out of Scope                                       |
|---------------|---------------------------------------------------------------|-----------------------------------------------------------------|------------------------------------------------------------|
| Feedback data | Minimal hash + sorted set model for feedback + sources       | `feedback:{uuid}`, `feedback:created`, `feedback:source:*`     | `feedback:unclustered` for vector clustering              |
| Clusters      | `cluster:{id}` + `cluster:items:{id}` for grouping feedback  | Same pattern via `backend/store.py` and dashboard clustering   | `clusters:all`, centroid field, issue/pr metadata on cluster |
| Config        | Single `config:reddit:subreddits` key for poller             | Same key used by backend + dashboard SourceConfig UI           | —                                                          |
| Jobs          | Not specified                                                | `job:{id}`, `cluster:jobs:{cluster_id}` for coding-agent jobs  | ECS/Fargate integration and job logs surfaced in UI        |
| Stats         | Optional `stats:source` hash for counts by source            | Not used; stats computed dynamically                           | —                                                          |
| Persistence   | Redis as primary, Postgres later for joins/history          | Redis/Upstash + in‑memory fallback only                        | Postgres schema remains future work                        |

---

## Goals
- Persist normalized feedback (Reddit, Sentry, manual) with simple filtering and recent-first listing.
- Deduplicate by external source ID (e.g., Reddit post id).
- Keep clustering support lightweight while leaving room to swap in a relational store later.

## Storage Choice
- **Redis (Upstash-friendly)** as the primary store for this hackathon: no schema migration, fast reads, works in serverless.
- Keep existing in-memory codepath as fallback when `REDIS_URL` is absent.
- Future swap: Postgres with equivalent tables/indices (outlined below) when we need joins and history.

## Redis Data Model
- `feedback:{uuid}` (hash): `id`, `source`, `external_id`, `title`, `body`, `metadata` (JSON string), `created_at`, optional UI fields (e.g. `github_repo_url`, `clustered`), plus any source-specific fields like `permalink`, `subreddit`, `score`, `num_comments`.
- `feedback:created` (sorted set): member = `uuid`, score = epoch seconds (for recent-first pagination).
- `feedback:source:{source}` (sorted set): member = `uuid`, score = epoch seconds (fast filter by source).
- `feedback:external:{source}:{external_id}` (string): value = `uuid` (dedupe guard to skip reprocessing).
- `feedback:unclustered` (set): feedback IDs pending vector-based clustering from the dashboard.
- `cluster:{uuid}` (hash): `id`, `title`, `summary`, `status`, `created_at`, `updated_at`, `github_pr_url`, and optional fields used by Soulcaster such as `centroid` (JSON-encoded vector), `issue_title`, `issue_description`, `github_repo_url`.
- `cluster:items:{uuid}` (set): feedback ids belonging to the cluster.
- `clusters:all` (set): IDs of all known clusters (used to list clusters efficiently).
- `job:{uuid}` (hash): coding-agent job metadata (`id`, `cluster_id`, `status`, `logs`, `created_at`, `updated_at`).
- `cluster:jobs:{cluster_id}` (sorted set): job IDs for a cluster, score = epoch seconds (for newest-first job history).
- `stats:source` (hash, planned/optional): counts by source (optional; can compute on read if small; not required by the current Soulcaster build).
- `config:reddit:subreddits` (string JSON array): global subreddit list used by the poller and dashboard SourceConfig UI.
- Optional TTL: apply TTL to feedback keys if we only need N days of backlog (not currently enabled in code; still a tuning knob).

## Core Operations
- **Insert feedback (backend ingest)**: Check `feedback:external:{source}:{external_id}`; if missing, write `feedback:{uuid}`, add to `feedback:created` and `feedback:source:{source}`, set external mapping. When feedback is ingested via the dashboard, it is also added to `feedback:unclustered` so vector clustering can pick it up.
- **List recent**: backend and dashboard list recent items by reading `feedback:created` (e.g. `ZRANGE feedback:created -100 -1 REV`) and hydrating each `feedback:{uuid}` hash.
- **Filter by source**: `ZRANGE feedback:source:{source}` with pagination for source-specific views.
- **Stats**: in the current Soulcaster build, stats are computed on read from `feedback:created`, `feedback:source:{source}`, and `clusters:all` rather than relying on a dedicated `stats:source` hash.
- **Clusters (backend path)**: backend clustering (`_auto_cluster_feedback`) creates or updates `cluster:{uuid}` hashes and `cluster:items:{uuid}` sets, and ensures the ID is present in `clusters:all`.
- **Clusters (vector path)**: dashboard vector clustering reads `feedback:unclustered`, generates embeddings via Upstash Vector + Gemini, assigns/creates clusters in Redis (`cluster:{uuid}`, `cluster:items:{uuid}`, `clusters:all`), marks affected `feedback:{uuid}` as `clustered=true`, and removes processed IDs from `feedback:unclustered`.
- **Jobs**: backend stores coding-agent jobs in `job:{uuid}` hashes and indexes them per cluster in `cluster:jobs:{cluster_id}`, enabling `GET /jobs`, `GET /jobs/{id}`, and `GET /clusters/{cluster_id}/jobs`.

## Future Postgres Sketch (for after hackathon)
- `feedback(id uuid pk, source text, external_id text, title text, body text, metadata jsonb, created_at timestamptz, permalink text, subreddit text, score int, num_comments int, UNIQUE(source, external_id))`
- `clusters(id uuid pk, title text, summary text, status text, created_at timestamptz, updated_at timestamptz, github_pr_url text)`
- `cluster_items(cluster_id uuid fk, feedback_id uuid fk, primary key (cluster_id, feedback_id))`
- Indexes: `(source)`, `(created_at desc)`, `(subreddit)`, `(source, external_id)`.

## Deployment Notes (Upstash/GCP)
- Configure `REDIS_URL` (Upstash URL) for the backend and poller; if unset, fallback to in-memory.
- Keep `READONLY`/`WRITE` separation only if using multi-endpoint Upstash plans; otherwise single URL is fine.
- Add a small `PING`/health check endpoint if we need runtime validation.

## Testing
- Unit tests should mock the Redis client and assert key writes/reads for insert, list, dedupe.
- Keep current API contracts intact (`backend/store.py` signatures) so the frontend and poller do not change.

---

## Current Soulcaster Implementation vs This Plan

This section is a status overlay; the “Redis Data Model” and “Core Operations” sections above describe the intended hackathon design, while the bullets below call out what’s implemented today, what’s still future work, and what we added beyond the original scope.

### Planned & Implemented

The following parts of the original Redis plan are live in Soulcaster:

- Planned keys that exist:
  - `feedback:{uuid}`, `feedback:created`, `feedback:source:{source}`, `feedback:external:{source}:{external_id}`.
  - `cluster:{uuid}`, `cluster:items:{uuid}`.
  - `config:reddit:subreddits`.
- Planned operations that exist:
  - Insert‑and‑dedupe on feedback via `feedback:external:{source}:{external_id}`.
  - Recent‑first listing via `feedback:created`.
  - Source filtering via `feedback:source:{source}`.
  - Cluster listing and hydration from `cluster:{uuid}` + `cluster:items:{uuid}`.
- Implementation details:
  - All of the above are wired through `backend/store.py` (InMemoryStore + RedisStore) and used by `backend/main.py`.
  - The in‑memory fallback path matches the “no Redis required for local dev” constraint.

### Planned but Not Yet Implemented or Only Partial

These items were part of the hackathon design but are still future or intentionally deferred:

- `stats:source`:
  - Documented as a hash for per‑source counts, but current dashboards compute counts at read time from existing sorted sets and cluster sets instead of maintaining this key.
- TTLs:
  - The plan calls out optional TTLs on feedback keys; the current codebase does not set expiries, so retention is effectively unlimited unless manually purged.
- Postgres mirror:
  - The Postgres schema and migration strategy outlined here have not been implemented; Redis/Upstash (or in‑memory) is the only backing store.

### Not Originally Planned but Implemented (Extras)

These keys and patterns are additional to the original minimal Redis plan:

- New keys:
  - `feedback:unclustered`: tracks feedback IDs pending vector‑based clustering from the dashboard.
  - `clusters:all`: a set of cluster IDs used to list clusters efficiently.
  - `job:{uuid}` and `cluster:jobs:{cluster_id}`: support coding‑agent job tracking for the Fargate‑based agent runner.
  - Extra fields on `cluster:{uuid}` such as `centroid`, `issue_title`, `issue_description`, `github_repo_url` to better integrate with the dashboard and coding agent.
- Dashboard‑side clustering:
  - Next.js clustering routes (`/app/api/clusters/run`, `/app/api/clusters/run-vector`, `/app/api/clusters/reset`) and `dashboard/lib/redis.ts` operate directly on the same Redis keyspace, using `feedback:unclustered`, `cluster:{uuid}`, `cluster:items:{uuid}`, and `clusters:all`.
  - Upstash Vector, via `dashboard/lib/vector.ts`, stores embeddings and performs ANN search; this sits alongside Redis and was not part of the original “Redis‑only” design.

For a full architecture view of how these keys are used end-to-end, see `documentation/current_architecture.md` and the backend store implementation in `backend/store.py`.
