# Database Design (Hackathon Redis Plan)

## Goals
- Persist normalized feedback (Reddit, Sentry, manual) with simple filtering and recent-first listing.
- Deduplicate by external source ID (e.g., Reddit post id).
- Keep clustering support lightweight while leaving room to swap in a relational store later.

## Storage Choice
- **Redis (Upstash-friendly)** as the primary store for this hackathon: no schema migration, fast reads, works in serverless.
- Keep existing in-memory codepath as fallback when `REDIS_URL` is absent.
- Future swap: Postgres with equivalent tables/indices (outlined below) when we need joins and history.

## Redis Data Model
- `feedback:{uuid}` (hash): `id`, `source`, `external_id`, `title`, `body`, `metadata` (JSON string), `created_at`, `permalink`, `subreddit`, `score`, `num_comments`.
- `feedback:created` (sorted set): member = `uuid`, score = epoch seconds (for recent-first pagination).
- `feedback:source:{source}` (sorted set): member = `uuid`, score = epoch seconds (fast filter by source).
- `feedback:external:{source}:{external_id}` (string): value = `uuid` (dedupe guard to skip reprocessing).
- `cluster:{uuid}` (hash): `id`, `title`, `summary`, `status`, `created_at`, `updated_at`, `github_pr_url`.
- `cluster:items:{uuid}` (set): feedback ids belonging to the cluster.
- `stats:source` (hash): counts by source (optional; can compute on read if small).
- `config:reddit:subreddits` (string JSON array): global subreddit list used by the poller.
- Optional TTL: apply TTL to feedback keys if we only need N days of backlog.

## Core Operations
- **Insert feedback**: Check `feedback:external:{source}:{external_id}`; if missing, write `feedback:{uuid}`, add to `feedback:created` and `feedback:source:{source}`, set external mapping.
- **List recent**: `ZRANGE feedback:created -100  -1 REV` (with offset/limit) then `HMGET` each id.
- **Filter by source**: `ZRANGE feedback:source:{source}` with pagination.
- **Stats**: use `stats:source` counters or compute by set cardinality if small.
- **Clusters**: store cluster hash + membership set; to enrich, fetch each `feedback:{id}`.

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
