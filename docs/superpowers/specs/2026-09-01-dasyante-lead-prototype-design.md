# Dasyante Lead Research Prototype Design

## Goal

Turn a CSV of candidate companies into evidence-backed Dasyante leads while keeping contact enrichment behind a qualification gate.

## Scope
The first prototype is a local Python CLI. It accepts company name, website, and optional LinkedIn URL. It searches public web sources with Tavily, fetches selected public pages with TinyFish Fetch, extracts eight Dasyante signals, calculates a deterministic score, and writes a reviewable SQLite/CSV result. Apollo Basic is used through a human-selected UI/CSV export after qualification; the prototype imports that CSV and optionally uses Hunter for email lookup and verification.

The prototype does not scrape LinkedIn, automate Sales Navigator, send email, send LinkedIn messages, or use Instagram data.

## Data flow

```text
CSV -> normalize/dedupe -> Apollo company profile (7-day cache)
    -> Tavily search -> allowlisted URLs -> TinyFish Fetch
    -> evidence records -> deterministic score -> review queue
    -> Apollo people lookup -> Hunter email lookup/verification -> approved export
```

## Boundaries

- Provider clients use service-specific authentication with keys loaded from the ignored local `.env` file or environment variables. Local file values take precedence over shell exports.
- Missing keys fail with an actionable error; the pipeline never invents provider data.
- LinkedIn is excluded from automated fetches.
- Company qualification and contact enrichment are separate states.
- Apollo company metadata provides context before research, never evidence-score points. Its failures are visible and nonfatal; refresh failures preserve the last profile. Company discovery and People Search are blocked by the current trial plan, so company intake and contact selection remain CSV-based.
- Evidence stores the quote, URL, source tier, retrieval time, and review state.
- Outreach is draft-only and human-approved.

## Scoring

The score has eight weighted signals totaling 100: customer-facing AI agent (18), persistent or multi-session memory (18), reliability/evaluation/grounding pain (16), relevant hiring (15), multi-model or agent-framework evidence (10), AI-generated recommendations/actions (8), enterprise or regulated consequence (7), and recent launch/scale (8). YES contributes the evidence-adjusted weight, UNKNOWN contributes zero, and contradictory evidence requires review.

## Verification

Tests cover URL normalization, duplicate removal, evidence extraction, score bounds, qualification gates, and the invariant that contact enrichment cannot run for unqualified companies. A local fixture smoke test covers the full pipeline without requiring network keys. A live smoke test runs only when provider keys are supplied.
