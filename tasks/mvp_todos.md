# FeedbackAgent MVP Todos

## Shared Setup & Decisions
- [x] Confirm target GitHub repo and base branch @Sam @Shared
- [ ] Choose LLM provider(s) & models (Embeddings, Summarization, Code-gen) @Sam @LLM
- [ ] Generate GitHub token with repo access and set env vars @Sam @Backend
- [ ] Create .env.example for backend @Sam @Shared
- [x] Decide on DB (In-memory/Redis selected) @Sam @Backend

## Backend (Sam)
### Core & Ingestion
- [x] Scaffold FastAPI app @Sam @Backend
- [x] Define data models (FeedbackItem, IssueCluster) @Sam @Backend
- [x] Implement in-memory/Redis store @Sam @Backend
- [x] Implement /ingest/reddit endpoint @Sam @Backend
- [x] Implement /ingest/sentry endpoint @Sam @Backend
- [x] Normalize Sentry payloads @Sam @Backend
- [x] Implement GET /clusters @Sam @Backend
- [x] Implement GET /clusters/{id} @Sam @Backend
- [x] Implement POST /clusters/{id}/start_fix (Stub) @Sam @Backend
- [x] Implement Reddit poller (JSON-based) @Sam @Backend
- [x] Hook Reddit poller to /ingest/reddit @Sam @Backend
- [x] Add logging for Reddit poller @Sam @Backend

### Intelligence & Agents (Frontend/Serverless)
- [x] Add LLM dependencies (xenova/transformers) @Colleague @Frontend
- [x] Implement EmbeddingClient wrapper (clustering.ts) @Colleague @Frontend
- [ ] Implement LLMClient wrapper (summarize, propose_fix, choose_files) @Sam @Backend @LLM
- [x] Implement clustering logic (Embeddings + Cosine Similarity) @Colleague @Frontend
- [x] Implement triage worker (Process FeedbackItems -> IssueClusters) @Colleague @Frontend
- [x] Add embedding computation for new feedback on ingest @Colleague @Frontend
- [ ] Implement LLM summarization for new IssueClusters @Sam @Backend @LLM
- [x] Store cluster embedding_centroid @Colleague @Frontend

### Coding Agent (External AWS Service)
### Coding Agent (External AWS Service)
- [ ] Obtain AWS Agent API endpoint and credentials @Sam @Backend
- [ ] Implement AgentClient wrapper (send prompt -> receive PR URL) @Sam @Backend
- [ ] Update /clusters/{id}/start_fix to call AgentClient @Sam @Backend
- [x] Implement Job tracking API (POST/PATCH /jobs) @Sam @Backend
- [ ] Update IssueCluster with PR URL from Agent response @Sam @Backend
- [ ] Add logging for Agent API calls @Sam @Backend

### Deprecated / Handled by AWS Agent
- [x] Integrate PyGithub and connect to repo (Handled by AWS Agent)
- [x] Fetch and cache repo file tree (Handled by AWS Agent)
- [x] Implement candidate file selection (Handled by AWS Agent)
- [x] Implement coding agent pipeline (Handled by AWS Agent)
- [x] Implement Python syntax check (Handled by AWS Agent)
- [x] Implement branch creation via PyGithub (Handled by AWS Agent)
- [x] Implement file updates via PyGithub (Handled by AWS Agent)
- [x] Implement PR creation via PyGithub (Handled by AWS Agent)

## Frontend (Colleague)
- [x] Scaffold Next.js app @Colleague @Frontend
- [x] Set up basic styling @Colleague @Frontend @UI
- [x] Implement /api/clusters proxy @Colleague @Frontend
- [x] Implement /api/clusters/[id] proxy @Colleague @Frontend
- [x] Implement /api/clusters/[id]/start_fix proxy @Colleague @Frontend
- [x] Wire clusters list page to live data @Colleague @Frontend
- [x] Wire cluster detail page to live data @Colleague @Frontend
- [x] Add "Generate Fix" button @Colleague @Frontend @UI
- [ ] Implement polling of cluster detail after Generate Fix @Colleague @Frontend
- [ ] Display status badges (new, fixing, pr_opened, failed) @Colleague @Frontend @UI
- [ ] Display PR link when available @Colleague @Frontend @UI
- [ ] Display error message if failed @Colleague @Frontend @UI
- [ ] Add Reddit vs Sentry source badges @Colleague @Frontend @UI

## Prompts & Instructions
- [ ] Define triage summarization prompt @Sam @LLM
- [ ] Define coding agent patch-generation prompt @Sam @LLM
- [ ] Define fallback prompt for file selection @Sam @LLM
- [ ] Add README note text for auto-generated PRs @Sam

## Testing & Demo
- [x] Create sample feedback fixtures (seed_mock_data in main.py) @Sam @Backend
- [ ] Create sample Sentry webhook fixture/curl script @Sam @Backend
- [ ] Run end-to-end test @Sam @Colleague
- [ ] Capture repo/PR URL examples @Sam
- [ ] Rehearse demo narrative @Sam @Colleague
