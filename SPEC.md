# Apollo company-profile stage

## Approved scope

The user selected "Company profiles" on 2026-10-03: automatically enrich company metadata before web research, cache for seven days, show metadata in the workspace/export, and continue with a visible warning if Apollo fails. Company discovery and People Search are blocked by the current Basic (Trial) plan; they are not part of this change.

## Behavior and boundaries

- Pipeline: CSV → Apollo company profile → Tavily → TinyFish → evidence score → review → manual contacts/Hunter.
- Use `GET /api/v1/organizations/enrich?domain=...`, authenticated with the existing local key. Store only selected company fields, never credentials or contact records.
- Automatically enable profiles when `APOLLO_API_KEY` is configured; expose skip and refresh controls in the CLI and research modal.
- Success and not-found results are reusable for seven days; errors must remain visible and retry on the next run. Refresh explicitly bypasses the cache.
- Retain the original successful profile if a refresh fails, but display the failure; do not count it as a fresh result.
- Store industry, headcount, location, funding, technologies, Apollo ID, retrieval time, status and error in a separate additive SQLite table. Existing candidates, evidence and contacts must survive.
- Apollo metadata is context, not evidence for agent/memory/reliability signals; do not modify the fit score or qualification/contact gates.
- Estimate up to one company-enrichment credit per uncached candidate. The approved hosted pipeline does not call discovery or People Search; the current trial key permits legacy organization search but denies People API search.
- Keep CSV intake and the supported manual contact workflow. No new dependencies, outreach, scraping of LinkedIn, or account mutations.

## Acceptance and scorecard

All of these must pass before completion:

1. `python3 -m unittest discover -v`: legacy tests and new profile/cache/failure/CLI/HTTP tests pass offline.
2. Adapter tests prove the domain, method, endpoint and authentication header, and handle missing/malformed results safely.
3. Pipeline tests prove Apollo executes before web search; fresh cache avoids another call; expiry/refresh cause a call; errors do not abort research or raise scores; contact gates remain intact.
4. JSON and CSV export contain company context; API/dashboard and UI show profile fields, cached/not-found/error state, and retrieval time.
5. `node --check web/app.js` succeeds; live validation returns an authentic company profile and confirms a cached second lookup does not increase Apollo usage.
6. Restart only the local server started in this session; `http://127.0.0.1:8765/api/health` and dashboard pass with existing test leads intact.

Fast feedback: focused unittest files after each implementation slice, expected under two seconds. Final feedback: full offline suite, syntax check, one bounded live profile/research test, and HTTP verification. Stop when the checklist passes or a live provider blocker is explicitly reported. No long-run working-memory files or Codex configuration changes are needed.

## Hosted phase (approved 2026-10-03)

The user requests full frontend verification, a Vercel deployment through their authenticated CLI, JSONBin persistence using the supplied master key, and hosted end-to-end testing. They explicitly chose no login/security layer and migration of all three existing test leads, including contact data. The public exposure and provider-credit risk were explained and accepted.

- Deploy a new project named `dasyante-lead-research` in the CLI's active team, not the unrelated existing `dasyante-site` project.
- Keep all credentials in server-side Vercel environment variables. Exclude `.env`, test databases, reports, and local tooling from uploads and function bundles.
- Use the existing standard-library Python handler as a Vercel function and serve the existing vanilla frontend. Do not add application dependencies.
- JSONBin is the hosted source of truth. Use a dedicated private collection and append-only mutation records rather than overwriting a shared JSON document, so concurrent function instances cannot silently erase each other's writes. An in-memory SQLite projection may reuse existing query/scoring logic; no on-disk SQLite is used as hosted persistence.
- Migrate current evidence, timestamps, Apollo profiles, scores, review state, contacts and usage without modifying local data. Record the collection ID locally and in Vercel secrets.
- Keep reads fail-closed on invalid/unreachable storage. A mutation is acknowledged only after JSONBin persistence succeeds. Do not silently fall back to local storage.
- Process frontend CSV batches one company per API request, with progress and per-company errors, to fit serverless time limits. Maintain profile caches and contact review gates.
- Repair actual UI issues found by browser tests. Verify filtering/selection, modal interaction, CSV validation, Apollo controls, research, review, contact import, profile/evidence display, contact verification display, downloads, and mobile layout.
- Hosted app is public by request; JSONBin bins remain private and the master key is never sent to the browser. Do not expose arbitrary admin or fixture endpoints.
- Document JSONBin request/bin-size growth and the public-access tradeoff. Do not claim this small prototype is a high-volume database system.

### Hosted acceptance scorecard

1. Full offline suite and JavaScript syntax check pass, including JSONBin replay/pagination/private headers, durable reopen, write failure, concurrent mutation preservation, migration and hosted storage selection.
2. A real local-browser run covers the UI interactions above at desktop and mobile widths, with no application JavaScript errors or horizontal overflow. Fixtures are isolated from real leads/keys.
3. The Vercel production URL serves the frontend and functioning API, with all three migrated leads and the verified contact intact.
4. Hosted write followed by a separate request proves JSONBin persistence. A bounded real research run exercises Apollo/Tavily/TinyFish; review and contact workflows are tested without sending outreach.
5. A real hosted browser automation validates interaction paths. Secrets are absent from HTML, JavaScript, API exports and accessible files such as `/.env`.
6. Final response includes the hosted URL, local/browser/API test outcomes, provider limits and any remaining blocker. Stop when these checks pass or report the exact external blocker; never present partial deployment as fully verified.
