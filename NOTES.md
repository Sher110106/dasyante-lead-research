# Hosting notes

- Apollo company enrichment works. The current key can also call the legacy `POST /api/v1/organizations/search` endpoint, while `mixed_companies/search` and all People API search endpoints return `API_INACCESSIBLE` for the Basic (Trial) team. Apollo's web People search remains available for manual CSV export.
- The organization-search request originally omitted `Content-Type: application/json`, so Apollo silently ignored the query and returned generic organizations. The client now sends the header, and `dasyante discover --query Mem0` returns Mem0, Memora and mem0ry as expected.
- User explicitly declined authentication and approved migration of the current contact-bearing test leads. Public visibility/credit-spend risk was explained.
- Vercel CLI 54.9.1 is authenticated; a distinct project will be used rather than `dasyante-site`.
- JSONBin returned Cloudflare 403/1010 with Python's default User-Agent. A descriptive application User-Agent authenticated successfully; zero existing collections were listed. Add a regression test for this client header.
- Vercel supports BaseHTTPRequestHandler subclasses in `api/`; no backend framework dependency is needed.
- JSONBin update API lacks a documented conditional-write mechanism. Append-only mutation bins in a dedicated collection preserve concurrent writes; read reconstruction grows with history, so this remains a small-workspace prototype.
- Playwright testing tools are installed only in the approved temporary directory, not as application dependencies.
- Hosted deployment is live at https://dasyante-lead-research.vercel.app using a new Vercel project and a dedicated private JSONBin collection. The migrated snapshot contains three companies, one qualified/reviewed lead, one verified contact, Apollo profiles and evidence.
- The HTTP layer now opens the configured backend per request and flushes hosted mutations before returning success. Hosted research rejects multi-company API payloads; the browser submits one company per request with progress and per-company failures.
- Hosted verification passed for health, dashboard, JSON/CSV downloads, independent write/read persistence, a bounded Apollo/Tavily/TinyFish run, secret-surface checks and desktop/mobile browser interaction. JSONBin history currently contains one snapshot and two mutation records.
