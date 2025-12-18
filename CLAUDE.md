# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Soulcaster** is a feedback triage and automated fix generation system. It ingests bug reports from Reddit, Sentry, and GitHub issues, clusters similar feedback using embeddings, and triggers a coding agent to generate fixes and open PRs.

**Flow**: Reddit/Sentry/GitHub → Clustered Issues → Dashboard Triage → Coding Agent → GitHub PR

## Architecture

Three components sharing Upstash Redis:

1. **Backend** (`/backend`) - FastAPI service for ingestion, clustering, and agent orchestration
2. **Dashboard** (`/dashboard`) - Next.js 16 (App Router) web UI for triage and management
3. **Coding Agent** (`/coding-agent`) - Standalone script that fixes issues via E2B sandboxes

### Tech Stack

- **Backend**: FastAPI, Pydantic, redis-py, Upstash REST, Gemini embeddings, E2B sandboxes
- **Dashboard**: Next.js 16, TypeScript, Tailwind, NextAuth (GitHub OAuth), Prisma (PostgreSQL)
- **Storage**: Upstash Redis + Upstash Vector for embeddings
- **LLM**: Gemini (`gemini-embedding-001` for embeddings, `gemini-2.5-flash` for summaries)

## Development Commands

### Backend (from project root)

```bash
pip install -r backend/requirements.txt

uvicorn backend.main:app --reload --port 8000   # API server
python -m backend.reddit_poller                  # Reddit poller (separate process)

pytest backend/tests -v                          # All tests
pytest backend/tests/test_clusters.py -v         # Single test file
pytest backend/tests/test_clusters.py::test_list_clusters -v  # Specific test
```

### Dashboard (from `/dashboard`)

```bash
npm install
npx prisma migrate dev        # Setup/migrate database
npx prisma generate           # Regenerate Prisma client

npm run dev                   # Development server (port 3000)
npm run build                 # Production build (runs prisma generate first)
npm run lint                  # ESLint
npm run format                # Prettier
npm run type-check            # TypeScript check
npm test                      # Jest tests
npm run test:watch            # Jest watch mode
```

### Coding Agent

```bash
python coding-agent/fix_issue.py <github-issue-url> --job-id <optional-job-id>
```

## Key Files

**Backend**:
- `backend/main.py` - FastAPI routes (`/ingest/*`, `/clusters`, `/feedback`, `/jobs`, `/cluster-jobs`)
- `backend/store.py` - Redis/in-memory storage abstraction
- `backend/models.py` - Pydantic models (`FeedbackItem`, `IssueCluster`, `AgentJob`)

**Dashboard**:
- `dashboard/lib/vector.ts` - Vector DB-based clustering (recommended)
- `dashboard/lib/clustering.ts` - Legacy centroid-based clustering
- `dashboard/lib/redis.ts` - Upstash Redis client helpers
- `dashboard/app/api/clusters/run-vector/route.ts` - Vector clustering endpoint
- `dashboard/prisma/schema.prisma` - Database schema (auth, projects)

## Redis Data Model

```
feedback:{id}        - Hash: id, source, title, body, metadata, created_at, clustered
feedback:created     - Sorted set: all feedback IDs by timestamp
feedback:unclustered - Set: IDs pending clustering
cluster:{id}         - Hash: id, title, summary, status, centroid, issue_title
cluster:items:{id}   - Set: feedback IDs in cluster
clusters:all         - Set: all cluster IDs
job:{id}             - Hash: id, cluster_id, status, logs, created_at
```

## Clustering Algorithm (Vector-Based)

1. Generate embedding via Gemini API for `title + body`
2. Query Upstash Vector for similar feedback items (top-K ANN search)
3. If top match ≥ 0.72 threshold AND already clustered → join that cluster
4. If top matches ≥ 0.72 but unclustered → create new cluster with all similar items
5. If no matches above threshold → create new single-item cluster
6. Store embedding in Vector DB with cluster assignment metadata
7. Generate LLM summary for new/changed clusters

## Environment Variables

**Backend** (`.env` in project root):
```bash
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
GEMINI_API_KEY=
GITHUB_ID=                    # GitHub OAuth client ID
GITHUB_SECRET=                # GitHub OAuth client secret
E2B_API_KEY=                  # For E2B sandbox provisioning
KILOCODE_TEMPLATE_NAME=kilo-sandbox-v-0-1-dev
```

**Dashboard** (`.env.local` in `/dashboard`):
```bash
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
UPSTASH_VECTOR_REST_URL=
UPSTASH_VECTOR_REST_TOKEN=
GEMINI_API_KEY=
GITHUB_ID=
GITHUB_SECRET=
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=              # Generate: openssl rand -base64 32
DATABASE_URL=postgresql://user:password@localhost:5432/soulcaster
BACKEND_URL=http://localhost:8000
```

## API Endpoints

**Backend** (`:8000`):
- `POST /ingest/reddit|sentry|manual` - Ingest feedback
- `GET /feedback` - List feedback (`?source=`, `?limit=`, `?offset=`)
- `GET /clusters`, `GET /clusters/{id}` - List/detail clusters
- `POST /clusters/{id}/start_fix` - Mark cluster as "fixing"
- `POST /cluster-jobs` - Trigger backend clustering job
- `POST /jobs`, `PATCH /jobs/{id}` - Manage agent jobs

**Dashboard** (`:3000/api`):
- `POST /api/clusters/run-vector` - Run vector-based clustering
- `POST /api/clusters/cleanup` - Merge duplicate clusters
- `POST /api/trigger-agent` - Trigger coding agent

## GitHub Authentication

- Users sign in via GitHub OAuth (required)
- Access token stored in encrypted NextAuth session
- PRs created from user's account (not a bot)
- Scopes: `repo`, `read:user`
