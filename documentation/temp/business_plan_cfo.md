# Soulcaster: The 30-Day Revenue Plan (CFO Edition)

**DATE:** December 7, 2025  
**STATUS:** Actionable  
**PREPARED BY:** CFO

## 1. Executive Summary

This document outlines a direct path to generating initial revenue from the Soulcaster technology within a 30-day window. The strategy is to monetize the core value proposition—automated code repair—by offering a paid, API-first service for private repositories, while leveraging the existing open-source project as a lead-generation engine.

The core principle is speed to market. We will bypass the traditional "freemium" SaaS model for private repos and instead offer immediate value for a clear price. Our target is not broad market adoption in the first month, but a focused acquisition of our first paying customers who have a clear and urgent need for this technology.

**The Objective:** Validate the market's willingness to pay by securing our first month's revenue, however small. This is a crucial data point that will inform all future investment and strategy.

For a more granular, short-term execution view, see `documentation/revenue_week1_mrr_plan.md`, which specifies a one-week plan to reach at least **$200 MRR** via 2–3 design-partner customers on the Starter plan.

## 2. The 30-Day Path to First Revenue

This is a week-by-week execution plan.

**Week 1: Productization & Pricing**

*   **Action:** Finalize a REST API for the "Generate Fix" functionality. The API will take a cluster of bug reports (or a single bug report) as input and return a link to a generated pull request.
*   **Authentication:** Implement simple API key authentication. No complex user accounts or OAuth. We can generate keys manually for our first customers.
*   **Pricing:** Establish a simple, usage-based pricing model. For example:
    *   **Pay-as-you-go:** \$10 per successfully generated pull request.
    *   **"Starter" package:** \$99/month for up to 15 pull requests.
*   **Payment:** Integrate a simple payment solution like Stripe or Lemon Squeezy. We need a way to take credit cards, fast.

**Week 2: Go-to-Market (GTM) & Lead Generation**

*   **Action:** Identify 100 potential customers. These are not random companies; they are teams that are actively using Sentry, have high-volume bug reports, and are active on GitHub. We can find them through GitHub, Sentry's website, and developer communities.
*   **Marketing:**
    *   Create a simple landing page that clearly articulates the API offering and pricing.
    *   Write one high-quality blog post titled "We Built a Bot to Automate Our Bug Fixes. Now You Can Use It." and share it on Hacker News, Reddit (/r/programming, /r/softwaredevelopment), and other developer forums.
    *   Direct outreach to the 100 identified leads.

**Week 3: Sales & Conversion**

*   **Action:** Engage with the leads generated in Week 2. Offer a free trial of 5 pull requests to qualified leads.
*   **Sales:** The "sales" process is a technical conversation with the team lead or a senior engineer. We are not selling a vision; we are selling a tool that solves a problem they have *today*.
*   **Conversion:** The goal is to convert at least one of these leads into a paying customer by the end of the week.

**Week 4: Support & Iteration**

*   **Action:** Provide direct, hands-on support to our first paying customers. Their success is our success.
*   **Feedback:** Gather feedback on the API, the pricing, and the overall experience. This feedback is more valuable than the initial revenue.
*   **Report:** At the end of the month, we will have two things:
    1.  Revenue in the bank.
    2.  Market validation and a clear direction for the next 90 days.

## 3. Product: The Paid API

The product is not the full dashboard; it is a simple, powerful API that does one thing well: it generates code fixes.

*   **Endpoint:** `POST /api/v1/generate-fix`
*   **Input:**
    ```json
    {
      "repository": "owner/repo",
      "issue": {
        "title": "Error in payment processing",
        "description": "...",
        "source_data": [ ... ]
      }
    }
    ```
*   **Output:**
    ```json
    {
      "job_id": "...",
      "status_url": "...",
      "pull_request_url": "..."
    }
    ```

This is a product that a developer can understand and integrate in an afternoon.

## 4. Go-to-Market (GTM) Strategy

Our GTM strategy is surgical and low-cost.

1.  **Leverage Open Source:** The open-source version of Soulcaster is our best marketing asset. We will add a prominent link to the paid API on the GitHub repository's README.
2.  **Content is King:** The blog post mentioned in Week 2 is crucial. It will be technical, authentic, and demonstrate the power of the tool.
3.  **Direct Outreach:** A personalized email to a team lead at a company that we know is struggling with bug volume is more effective than a thousand tweets.

## 5. Financials: A Back-of-the-Napkin Projection

The goal for the first month is not to be profitable, but to prove the model.

*   **Target:** 1 paying customer.
*   **Revenue (Month 1):** \$99 (assuming the "Starter" package).
*   **Cost (Month 1):**
    *   LLM API costs: Estimated at <\$20 for initial customers.
    *   Hosting: Minimal, as we are leveraging the existing infrastructure.
    *   **Total:** <\$100

**The ROI is not in the P&L; it is in the data. One paying customer proves more than a thousand sign-ups for a free trial.**

## 6. Team

The existing team is sufficient to execute this 30-day plan. We need to be ruthless in our focus and prioritize execution above all else. Every team member should be involved in the GTM and sales process. We are all on the hook for getting to our first dollar of revenue.
