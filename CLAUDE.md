# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**FeedbackAgent** is a self-healing dev loop MVP built for a 24-hour hackathon. The system ingests bug reports from Reddit and Sentry, uses LLM-based triage to cluster feedback into issues, and automatically generates code fixes via a coding agent that opens GitHub PRs.

**Flow**: Reddit/Sentry → Clustered Issues → Human triage dashboard → One-Click Fix → GitHub PR

## Architecture

### Three-Layer System ("Ears, Brain, Hands")

1. **The Ears (Ingestion Layer)**
   - Python service with Reddit poller (PRAW) and Sentry webhook endpoint
   - Normalizes feedback into `FeedbackItem` schema
   - In-memory storage (Python dicts) for MVP - no database

2. **The Brain (Triage + Coding Agents)**
   - Triage: Embedding-based clustering with cosine similarity (threshold: 0.8-0.85)
   - LLM generates cluster summaries
   - Coding Agent: Selects candidate files, generates patches, opens PRs

3. **The Hands (Execution)**
   - PyGithub integration for branch creation, commits, and PR opening
   - Syntax validation for Python files only (MVP scope)

### Tech Stack

**Backend (Python)**
- Currently not implemented
- Planned: FastAPI for HTTP server, PRAW for Reddit polling, PyGithub for GitHub integration

**Frontend (Next.js) - IMPLEMENTED**
- Next.js 16 App Router with TypeScript
- Upstash Redis for data persistence
- Tailwind CSS for styling
- `@xenova/transformers` for client-side embeddings (Xenova/all-MiniLM-L6-v2 model)
- Auto-clustering on page load when unclustered items exist
- Reddit ingestion UI for manual feedback submission
- Working directory: `/Users/sam/code/soulcaster/dashboard`

**Redis Data Model**:
- `feedback:{id}` - Hash with feedback details and `clustered: "true"|"false"`
- `feedback:unclustered` - Set of unclustered feedback IDs
- `feedback:created` - Sorted set of all feedback IDs by timestamp
- `cluster:{id}` - Hash with cluster metadata (title, summary, status, centroid)
- `cluster:items:{id}` - Set of feedback IDs in this cluster
- `clusters:all` - Set of all cluster IDs
- `reddit:subreddits` - Set of monitored subreddit names

**LLM Strategy**
- Fast/cheap model (e.g., Gemini Flash) for embeddings & summaries
- Stronger model (e.g., Claude Sonnet) for code generation
- Frontend uses Xenova transformers for local embedding generation

## Development Commands

### Backend (Python/FastAPI)

Currently not implemented. When implementing:

```bash
# Install dependencies
pip install -r requirements.txt  # or poetry install

# Run FastAPI server
uvicorn app.main:app --reload

# Run Reddit poller (separate process)
python scripts/reddit_poller.py

# Run tests (TDD approach per PRD)
pytest

# Run single test file
pytest tests/test_clustering.py -v
```

### Frontend (Next.js)

Working directory: `/Users/sam/code/soulcaster/dashboard`

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Run production build
npm start

# Lint and format
npm run lint
npm run format
npm run format:check

# Type checking
npm run type-check
```

**Note**: If dev server has memory issues, clean build cache:
```bash
pkill -f "next dev" && rm -rf .next && npm run dev
```

## Key Data Models

### FeedbackItem
- `id`: UUID
- `source`: "reddit" | "sentry"
- `external_id`: Original source ID
- `title`: Post title or truncated comment
- `body`: Full text content
- `metadata`: JSON (subreddit, permalink, stack frames, etc.)
- `created_at`: Timestamp
- `embedding`: Vector representation

### IssueCluster
- `id`: UUID
- `title`: LLM-generated (≤80 chars)
- `summary`: LLM-generated (≤300 chars)
- `feedback_ids`: List of associated FeedbackItem IDs
- `status`: "new" | "fixing" | "pr_opened" | "failed"
- `created_at`, `updated_at`: Timestamps
- `embedding_centroid`: Mean of member embeddings
- `github_branch`: Optional branch name
- `github_pr_url`: Optional PR URL
- `error_message`: Optional failure details

## API Endpoints

### Backend (Python/FastAPI) - NOT IMPLEMENTED
- Planned: `POST /ingest/reddit`, `POST /ingest/sentry`
- Planned: `GET /clusters`, `GET /clusters/{id}`, `POST /clusters/{id}/start_fix`

### Frontend API Routes (Next.js) - IMPLEMENTED
- `GET /api/clusters` - List all clusters from Redis
- `GET /api/clusters/unclustered` - Count unclustered feedback items
- `POST /api/clusters/run` - Run clustering algorithm on unclustered items
- `POST /api/clusters/reset` - Reset all clustering data (for debugging)
- `POST /api/feedback/ingest` - Ingest feedback from Reddit or manual submission
- `GET /api/config/reddit/subreddits` - Get monitored subreddits list
- `POST /api/config/reddit/subreddits` - Update monitored subreddits list

## Critical Implementation Details

### Clustering Logic (IMPLEMENTED)
**Location**: `lib/clustering.ts` and `app/api/clusters/run/route.ts`

1. Generate embeddings for all unclustered feedback (`title + body`)
2. For each feedback item, compare to all cluster centroids using cosine similarity
3. If similarity ≥ threshold: add to existing cluster and recalculate centroid
4. Else: create new cluster with this single feedback item
5. Generate/update cluster summary using simple heuristics (first title + body snippets)

**Similarity Threshold**: Configured in `app/api/clusters/run/route.ts:72`
- Default: `0.65` (65% similarity)
- Higher values (e.g., 0.8) = stricter matching, more clusters
- Lower values (e.g., 0.5) = aggressive grouping, fewer clusters

**Auto-Clustering**: Runs automatically on page load if unclustered items exist (silent mode)
- Implementation: `app/clusters/page.tsx:28-39`

**Debugging**: Use `POST /api/clusters/reset` to clear all clusters and re-run from scratch

### Candidate File Selection (Coding Agent)
1. **From Sentry feedback**: Extract filenames from stack traces, match against repo paths
2. **From text**: Extract keywords from cluster title, match file paths (case-insensitive)
3. **Limit**: Max 3-5 files, max 10k chars per file
4. **Fallback**: Send truncated file list to LLM for selection

### Patch Generation
- Prompt includes: cluster summary, feedback snippets, candidate file contents
- LLM returns JSON: `{files: [{path, updated_content}], summary}`
- Full-file replacement (no diff parsing in MVP)
- Python syntax check via `ast.parse()` before creating PR

### PR Creation Flow
1. Branch name: `feedbackagent/cluster-{id}-{slugified-title}`
2. For each file: fetch current SHA, update/create file on new branch
3. PR title: `Fix: {cluster.title}`
4. PR body includes: LLM summary, cluster summary, feedback source links, auto-generation notice
5. Update cluster: `status="pr_opened"`, set `github_branch` and `github_pr_url`

## Environment Variables

**Required for Dashboard** (create `.env.local` in `/dashboard`):

```bash
# Upstash Redis (required)
UPSTASH_REDIS_REST_URL=https://your-instance.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-token-here

# Reddit API (optional - for automated polling)
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=

# GitHub (not yet implemented)
GITHUB_TOKEN=  # Personal access token with repo scope
GITHUB_REPO=  # Format: "owner/repo"
BASE_BRANCH=main  # Target branch for PRs

# LLM Provider(s) (not yet implemented)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

## Scope Guardrails (MVP Only)

**What we HAVE built (Dashboard):**
- ✅ Reddit feedback ingestion (manual submission via UI)
- ✅ Feedback list view with source filtering
- ✅ Embedding-based clustering with auto-run
- ✅ Cluster list and detail views
- ✅ Upstash Redis persistence
- ✅ Reddit subreddit configuration UI

**What we are NOT building:**
- No auth/permissions (hardcoded env vars only)
- No multi-repo support
- No automated Reddit polling (manual submission only)
- No Sentry integration
- No coding agent / PR generation
- No robust retries/rate limiting
- No chat UI (click-to-fix only)
- No comprehensive test suite (manual verification)

## Known Limitations (Dashboard)

- Client-side embedding generation (loads Xenova model in browser)
- Simple heuristic summaries (no LLM summarization)
- Full-feedback clustering on each run (no incremental updates)
- No cluster merge/split UI
- No automatic PR merge or cluster closure
- Manual feedback submission only (no automated polling)

## Testing Strategy

Currently: Manual verification only

Future: Write tests for:
- Clustering logic (similarity thresholds, centroid updates)
- FeedbackItem normalization
- Redis data integrity
- API endpoint responses

## Post-Hackathon Future Work

**DO NOT implement these during MVP:**
- Automated Reddit polling with PRAW
- Sentry webhook integration
- Coding agent with PR generation (PyGithub)
- LLM-based cluster summarization
- Incremental clustering (only process new items)
- Cluster merge/split UI controls
- GitHub OAuth and multi-repo support
- Comprehensive observability and rate limiting
