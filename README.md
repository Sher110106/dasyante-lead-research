# Dasyante Lead Research Prototype

A local CLI for finding evidence-backed Dasyante prospects. It researches public company pages, scores the evidence, and keeps Apollo/Hunter contact enrichment behind a qualification and human-review gate.

## Providers

The first run can use free or trial allocations:

- Tavily: `TAVILY_API_KEY` for bounded public-web search.
- TinyFish Fetch: `TINYFISH_API_KEY` for public-page markdown extraction.
- Apollo: `APOLLO_API_KEY` for company profiles before research, plus Apollo UI/CSV export for manually selected decision makers.
- Hunter: optional `HUNTER_API_KEY` for email lookup and verification.

Copy `.env.example` to `.env` and add your keys there. The CLI and web server automatically load this local file; its values take precedence over existing shell exports. `.env` is ignored by Git and must never be committed. Restrict access with `chmod 600 .env`. You can select another credentials file with `DASYANTE_ENV_FILE`.

When `APOLLO_API_KEY` is configured, research first retrieves a company profile from Apollo: industry, employee count, location, funding and technologies. Profiles are cached in SQLite for seven days; Apollo errors are displayed as warnings without stopping public-web research. Metadata is company context, not proof of an AI agent or reliability/memory pain, and never adds fit-score points. The contact-selection workflow remains manual Apollo UI/CSV import. No Firecrawl credentials or CLI are needed.

Live checks with the current Basic (Trial) key allow organization enrichment and the legacy organization discovery endpoint (`POST /api/v1/organizations/search`). Apollo's current `mixed_companies/search` endpoint is still plan-gated. People API Search remains plan-gated on both the current and legacy endpoints; the Apollo web UI can still be used for manual People search and CSV export. Budget up to one company-enrichment credit per uncached company and one credit per organization-search page. Usage counters record attempted API calls, not the provider's billed credits.

## Commands

Search Apollo organizations with the trial-compatible discovery endpoint:

```sh
python3 -m dasyante discover --query "Mem0" --per-page 25
```

The command returns selected company fields that can be copied into the CSV research flow. It uses one Apollo organization-search page credit per request.

The current key returns HTTP 403 `API_INACCESSIBLE` for `mixed_people/api_search`, `people/search`, and `mixed_people/search`. The supported path for people on this account is:

1. Research and qualify a company.
2. Use Apollo's UI/CSV export to manually select decision makers.
3. Save those people in a CSV with `domain` or `candidate_id`, `first_name`, `last_name`, and `title`.
4. Let this prototype import that CSV only after the company is reviewed.

If a contact CSV has no email, Hunter can optionally find and verify it. Apollo API enrichment for people is reserved for a future paid API plan.

References:

- https://docs.apollo.io/reference/people-api-search
- https://docs.apollo.io/reference/people-enrichment

Dry-run the input without network access:

```sh
python3 -m dasyante research --input examples/candidates.csv --dry-run
```

Run public research:

```sh
python3 -m dasyante research --input candidates.csv --db dasyante.db
```

Skip Apollo company profiles or explicitly refresh their cache:

```sh
python3 -m dasyante research --input candidates.csv --db dasyante.db --skip-apollo
python3 -m dasyante research --input candidates.csv --db dasyante.db --refresh-apollo
```

The workspace's research modal offers the same skip/refresh controls. JSON exports include profile metadata, status, retrieval time and warnings; CSV exports include the company context columns. A failed refresh retains the previous profile with a visible warning.

Review a qualified candidate before contact-enrichment credits are used:

```sh
python3 -m dasyante review --db dasyante.db --candidate-id <id>
```

Example contact-selection CSV:

```csv
domain,first_name,last_name,title
acme.com,Jane,Doe,VP Engineering
```

Then enrich a reviewed company:

```sh
python3 -m dasyante enrich \
  --db dasyante.db \
  --candidate-id <id> \
  --contacts contacts.csv
```

Export JSON or CSV:

```sh
python3 -m dasyante export --db dasyante.db --output leads.json --format json
python3 -m dasyante export --db dasyante.db --output leads.csv --format csv
```

## Workspace UI

Open the local research cockpit:

```sh
python3 -m dasyante serve --db dasyante.db --port 8765
```

Then open `http://127.0.0.1:8765`.

The workspace provides:

- score and qualification overview
- candidate queue with filterable states
- evidence and source inspection
- Apollo company profiles, cached metadata and provider warnings
- human review approval
- Apollo CSV contact import
- optional Hunter lookup and verification
- CSV intake for new research runs

## Hosted workspace

The public hosted workspace is available at [dasyante-lead-research.vercel.app](https://dasyante-lead-research.vercel.app). It uses a dedicated private JSONBin collection as its durable source of truth. Vercel holds provider keys and JSONBin credentials server-side; the browser receives only dashboard, profile, evidence, contact and usage data.

The hosted research modal splits a pasted CSV into one-company requests, shows progress and per-company failures, and keeps the Apollo skip/refresh controls. JSON and CSV downloads are available from the workspace header. Hosted writes are acknowledged only after the append-only JSONBin mutation record is created. This keeps concurrent small-workspace writes from replacing one another, but the history grows with each mutation and is not intended as a high-volume database.

The deployed workspace was migrated from the live-test database with three companies, Apollo profiles, evidence, review state and one verified contact. Apollo company enrichment, Tavily search and TinyFish fetching were exercised once against the hosted API. Apollo discovery and People Search remain unavailable on the current Basic (Trial) plan, so contacts continue to use the reviewed manual CSV workflow.

## Safety rules

- LinkedIn URLs are rejected by the automated page fetcher.
- The prototype does not scrape Sales Navigator or send LinkedIn messages.
- Missing API keys fail clearly; the program never creates fake provider records.
- Contact enrichment requires both `qualified=1` and `reviewed=1`.
- Review opt-outs and suppression records before sending any outreach.

## Tests

```sh
python3 -m unittest discover -v
```
