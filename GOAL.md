<goal>
Preserve the completed Apollo stage; finish and browser-test the frontend, deploy the public workspace to Vercel with private JSONBin persistence, migrate existing test leads, and verify the hosted application.
</goal>
<context>
Read SPEC.md, dasyante/providers.py, pipeline.py, storage.py, cli.py, web.py, web/app.js, web/index.html, and tests/. The directory is not a Git repository; preserve current work and local secrets.
</context>
<constraints>
No outreach or blocked Apollo discovery/People Search. No application dependencies. Public workspace without login is explicitly requested; keys remain server-side and JSONBin bins private. Preserve local data. Avoid shared-document last-write-wins data loss and acknowledge writes only after persistence.
</constraints>
<scorecard>
Pass every acceptance item in SPEC.md. Score via focused/full unittest runs, JavaScript syntax check, a bounded live profile/cache check, and the local HTTP dashboard. Stop when all pass or report the exact blocker.
</scorecard>
<done_when>
Hosted acceptance scorecard in SPEC.md passes: offline tests, real local-browser interactions, durable JSONBin reads/writes, migrated records, production frontend/API, hosted browser test, bounded live providers, and no client-visible secrets.
</done_when>
<feedback_loop>
Run focused unittest tests after each slice (under two seconds). They exercise the provider, SQLite cache and pipeline directly. Escalate to the full suite and a real provider/HTTP check before completion.
</feedback_loop>
<workflow>
Test storage first, implement the JSONBin log and Vercel handler, finish frontend functionality and browser tests, provision private storage and Vercel environment variables, migrate and deploy, verify production, and report.
</workflow>
<working_memory>
Maintain PLAN.md and NOTES.md after significant findings, implementation/test milestones and deployment blockers. Keep secrets out of these files. CONTROL.md captures the approved public access, migration scope and bounded live-testing constraints.
</working_memory>
<verification_loop>
python3 -m unittest discover -v; node --check web/app.js; real company enrichment with a cached repeat; HTTP health/dashboard check at port 8765. Never describe mocks as live validation.
</verification_loop>
<execution_rules>
Preserve unrelated work, use patch for source edits, parallelize independent reads, test first, do not expose secrets or widen scope. Do not reset data or commit credentials. No Codex /goal runtime is required for this in-session execution.
</execution_rules>
<output_contract>
Ship the implementation, regression tests and updated README. Report Apollo's role, live/cache results, any plan restriction, and the local URL concisely.
</output_contract>
