# Soulcaster — One-Week $200 MRR Plan (CFO Edition)

This document operationalizes the high-level strategy in `business_plan.md` and `business_plan_cfo.md` into a concrete, one-week execution plan to reach at least **$200 in Monthly Recurring Revenue (MRR)**.

The intent is to be ruthlessly practical: use the current architecture (`documentation/current_architecture.md`), existing MVP work (`tasks/mvp_todos.md`), and the open-source repo as-is to land our first **2 design-partner teams at ~$99/month** (or equivalent mix that clears $200 MRR).

## 1. Objectives and Guardrails

- **Target MRR:** ≥ **$200** in active subscriptions by end of week.
- **Pricing anchor:** Reuse the "Starter" package from `business_plan_cfo.md`:
  - `$99/month` for up to N automated PRs/month (e.g., 10–15).
  - Month-to-month, cancel anytime.
- **Customer target:** 2–3 small teams (5–50 engineers) who:
  - Maintain at least one active GitHub repo.
  - Have recurring bug/incident volume (Sentry/Jira/GitHub issues).
  - Can integrate a simple GitHub-based workflow in under a day.
- **Scope constraint:** No net-new large features; only light wiring and docs on top of:
  - Backend ingestion + clustering (`backend/main.py`, `backend/store.py`).
  - Dashboard orchestration + agent trigger (`dashboard/app/api/*`).
  - Coding agent + AWS path (`coding-agent/fix_issue.py`, Fargate task).

Success is defined as **subscriptions started**, not just verbal commitments.

## 2. ICP and Offer (Day 1)

**Goal:** Lock in a painfully specific ideal customer profile and a single simple paid offer that Soulcaster can deliver with the existing stack.

- **ICP definition (CFO view):**
  - B2B SaaS companies, Seed–Series B, 5–50 engineers.
  - Using GitHub; ideally also Sentry or similar for error tracking.
  - Feeling pain around:
    - Aging bug backlogs.
    - Slow mean-time-to-resolution for regressions.
    - Lack of staff for "maintenance work."
- **Primary buyer:** Engineering manager / Head of Engineering.
- **Champion:** Senior engineer or tech lead on the most active service.

**Offer framing:**

- Product name: **"Bugfix Automation Starter"**.
- Plan: `$99/month`, cancel anytime, for one repo / team.
- Value promise in one sentence:
  - > "We turn your noisy error backlog into reviewed, ready-to-merge PRs every week—without adding headcount."
- Deliverables:
  - Integration support for one GitHub repo.
  - Automatic clustering of feedback into issues (Reddit/Sentry/manual today).
  - Coding agent that produces PRs for prioritized issues (design-partner level support).
  - Weekly summary of PRs opened and issues impacted (manual if necessary).

**Outputs by end of Day 1:**

- A short **one-pager** (Notion or Markdown) summarizing:
  - ICP, pricing, guarantee (e.g., "At least one useful PR in the first month or we refund the subscription").
  - Very basic onboarding checklist.
- A **landing stub**:
  - Either a simple page or section in `README.md` linking to the paid offer.

## 3. System Readiness Checklist (Days 1–2)

**Goal:** Confirm that the path from "clicking buy" to "seeing a PR" is real and repeatable for a design-partner customer, based on the current architecture.

Use `documentation/current_architecture.md`, `documentation/db_design.md`, and `coding-agent` docs as the ground truth.

- **Backend & storage:**
  - Ensure a stable deployment of `backend/main.py` with Redis/Upstash configured, matching `documentation/db_design.md`.
  - Verify `/ingest/*` endpoints and `/clusters`/`/jobs` are reachable from the dashboard environment.
- **Dashboard + agent trigger:**
  - Confirm `/api/clusters/*` and `/api/trigger-agent` work for at least one internal repo.
  - Validate the ECS/Fargate path (`coding-agent/fix_issue.py`, `coding-agent/FARGATE_DEPLOYMENT.md`) for a single happy-path issue.
- **Observability for design partners:**
  - Minimal logging for:
    - Cluster creation and status changes.
    - Agent job status updates and PR URLs.
  - This can be console logging / CloudWatch level as long as it is usable in support.

If any of the above are missing, treat them as **Day 1–2 unblockers**, not multi-week projects.

## 4. Pipeline and Outreach (Days 2–5)

**Goal:** Build and work a small but high-quality pipeline sufficient to close ≥2 design partners.

Leverage:

- `business_plan.md` market analysis and positioning.
- `tasks/mvp_todos.md` to understand current feature surface and gaps.

**4.1 Lead list construction (Day 2)**

- Assemble a list of **30–50** strong-fit targets:
  - Companies visible on GitHub with active issue trackers.
  - Maintainers of repos with recurring bug labels (e.g., `bug`, `regression`).
  - Teams in your extended network (alumni, ex-colleagues, incubator cohorts).
- For each lead, capture:
  - Repo(s) and key services.
  - Recent incident/bug activity (issues, Sentry-like signals where visible).
  - Likely buyer (name, title) and champion.

**4.2 Messaging and channel plan (Days 2–3)**

- Prepare **two short outbound scripts**, tailored to:
  - Warm intros.
  - Cold developer/EM outreach.
- Keep messages:
  - ≤4 sentences.
  - Concrete and anchored on saved time and reduced maintenance load.
- Ask for **a 15-minute call**, not generic feedback.

**4.3 Outreach execution (Days 3–5)**

- Send **15–20 personalized messages/day** across:
  - Email and LinkedIn.
  - Direct messages in relevant communities (Slack/Discord/GitHub Discussions).
- On calls:
  - Spend the first 10 minutes understanding:
    - Current bug triage and fix workflow.
    - Cost in time and frustration.
  - Show only the flows we can reliably deliver:
    - How feedback becomes clusters.
    - How a "Generate Fix" request leads to a PR.
  - Soft-close with a simple ask:
    - > "If we can get you one useful bugfix PR in the first month, is `$99/month` for this repo reasonable?"

Track funnel metrics in a simple spreadsheet or doc:

- Outreach → replies.
- Replies → calls.
- Calls → offers extended.
- Offers → subscribed.

## 5. Conversion and MRR Lock-In (Days 5–7)

**Goal:** Turn qualified interest into live subscriptions and ensure the first design partners get value quickly enough to stick.

**5.1 Offer shaping and urgency**

- Use the 30-day plan in `business_plan_cfo.md` as the umbrella:
  - Position this week as the **"Week 1 pilot"** of the broader paid API.
- For this week only, consider:
  - Locking in **founding-customer pricing** at `$99/month` for 12 months.
  - Including **concierge support** (you will manually shepherd early PRs if automation is flaky).

**5.2 Closing mechanics**

- On any call where fit is clear:
  - Propose a concrete start date within the week.
  - Walk the buyer through:
    - GitHub access requirements.
    - Any env/infra needs (GitHub App, tokens as described in README and `AGENTS.md`).
  - Share a Stripe (or equivalent) checkout link while still on the call.
- Aim to have **at least 2 teams**:
  - Completed checkout.
  - Provided repo details.
  - Scheduled for onboarding within a few days.

**5.3 Onboarding and retention safeguards**

- For each signed customer:
  - Schedule a 30–45 minute onboarding session.
  - Configure their repo and environment ahead of the call so you can demo a near-term fix path live.
- During the first month:
  - Ensure at least one useful PR is opened per customer.
  - Capture qualitative feedback to feed back into `tasks/mvp_todos.md` and architecture docs.

## 6. Reporting Back to the Team

At the end of the week, the CFO should be able to report:

- **MRR:** Total new MRR from design-partner subscriptions (target: ≥$200).
- **Pipeline health:**
  - Number of qualified leads still in consideration.
  - Reasons for wins and losses.
- **Product readiness:** Gaps uncovered in:
  - Backend and clustering pipeline.
  - Dashboard UX for clusters and jobs.
  - Coding agent reliability.

These insights should feed directly into:

- Updates to `business_plan_cfo.md` (longer-term revenue roadmap).
- Refinements to `documentation/current_architecture.md` and `documentation/db_design.md`.
- Next iterations of `tasks/mvp_todos.md` to systematically close the gaps that block higher MRR.

