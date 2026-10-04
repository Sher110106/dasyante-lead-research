# Dasyante Lead Research Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local CLI that turns 100 candidate companies into 10–30 evidence-backed Dasyante leads, then optionally enriches only qualified companies with Apollo and Hunter.

**Architecture:** A small Python package uses SQLite for durable state, standard-library HTTP clients for Tavily, Firecrawl, Apollo, and Hunter, and deterministic scoring over stored evidence. The CLI separates research, qualification, review, and contact enrichment so provider credits cannot be spent on rejected companies.

**Tech Stack:** Python 3.12+, SQLite, `urllib`, `argparse`, `unittest`, CSV/JSON.

---

### Task 1: Core models and scoring

**Files:**
- Create: `dasyante/models.py`
- Create: `dasyante/scoring.py`
- Test: `tests/test_scoring.py`

- [ ] Write failing tests for URL normalization, score bounds, YES/UNKNOWN handling, and qualification gates.
- [ ] Run `python -m unittest tests.test_scoring -v` and confirm failure because the package is absent.
- [ ] Add dataclasses for `Candidate`, `Evidence`, and `SignalResult`.
- [ ] Add the eight weighted signals totaling 100 and a pure `score_signals()` function.
- [ ] Run the focused tests and confirm they pass.

### Task 2: Provider adapters

**Files:**
- Create: `dasyante/providers.py`
- Test: `tests/test_providers.py`

- [ ] Write tests for missing-key errors, URL allowlisting, request payload shape, and HTTP error reporting using a local test HTTP server.
- [ ] Run the focused tests and confirm failure before implementation.
- [ ] Implement Tavily basic search at `POST https://api.tavily.com/search` with four bounded query themes.
- [ ] Implement Firecrawl v2 scrape at `POST https://api.firecrawl.dev/v2/scrape` with markdown output and `onlyMainContent`.
- [ ] Implement Apollo Basic CSV import for manually selected contacts; do not call either inaccessible Basic-plan People API endpoint.
- [ ] Implement Hunter email finder and verifier behind `HUNTER_API_KEY`.
- [ ] Raise explicit configuration and provider errors; never return fake records.
- [ ] Run focused tests and confirm they pass.

### Task 3: Pipeline, storage, and CLI

**Files:**
- Create: `dasyante/storage.py`
- Create: `dasyante/pipeline.py`
- Create: `dasyante/cli.py`
- Create: `dasyante/__main__.py`
- Create: `examples/candidates.csv`
- Test: `tests/test_pipeline.py`

- [ ] Write failing tests for CSV loading, deduplication, evidence persistence, score persistence, and the no-contact-enrichment gate.
- [ ] Run the focused tests and confirm failure before implementation.
- [ ] Implement SQLite tables for candidates, evidence, signals, contacts, and usage counters.
- [ ] Implement research with two triage pages per company and a public-domain allowlist that excludes LinkedIn.
- [ ] Implement deterministic signal extraction with quoted excerpts and source metadata.
- [ ] Implement `research`, `review`, and `enrich` CLI commands with JSON/CSV output.
- [ ] Ensure `enrich` refuses any company that has not passed qualification and review.
- [ ] Run focused tests and confirm they pass.

### Task 4: Configuration and smoke verification

**Files:**
- Create: `README.md`
- Create: `.env.example`
- Create: `tests/test_smoke.py`

- [ ] Write a local fixture smoke test that processes candidates without network access and produces qualified output.
- [ ] Run the smoke test and confirm it fails before wiring the CLI.
- [ ] Add setup, free-tier key instructions, commands, cost counters, and compliance limits to README.md.
- [ ] Add environment variable names without real credentials.
- [ ] Run all tests with `python -m unittest discover -v`.
- [ ] Run `python -m dasyante --help` and the local fixture command.
- [ ] If trial keys are present, run one-company live research and verify usage counters before scaling.
