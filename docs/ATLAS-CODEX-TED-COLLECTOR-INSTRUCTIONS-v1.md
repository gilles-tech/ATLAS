# ATLAS MARCHÉS — TED Collector Recovery v1
Date: 2026-11-01
Scope: installed local collector ONLY. No unrelated products, no UI redesign, no full reimport.

## Verified facts
- Live DB: ~/AtlasMarches/data/atlas.db. Last verified: 108,346 notices (BOAMP 3,146; TED 105,200).
- FTS5 external-content index `opportunities_fts` had failed its integrity check with 'database disk image is malformed'; repaired on the active DB using `rebuild`, then FTS5 integrity-check rank=1 and SQLite integrity_check both PASS.
- Backups: ~/AtlasMarches/backups/pre-repair-20261101-093313/atlas.db and ~/AtlasMarches/backups/before-live-fts-rebuild-20261101-094241.db. Preserve them.
- BOAMP post-repair run reported `ok`, count=3000 processed and +13 distinct notices.
- TED runner PID 7200 was still running at last observation; sampling showed Python `_buffered_readline` -> SSL read -> poll, i.e., waiting for HTTPS response content. The specific API call and root cause are not yet known.
- Last verified full run absent; APProch and EU_FT_TENDERS/EU_FT_GRANTS parsers failed separately. `feeds.json` has no enabled feeds.
- Collector installation: ~/Library/Application Support/AtlasMarches/collector/{app.py,sync_engine.py,sync_daily.py,run-collector.sh}; LaunchAgent label `fr.atlasmarches.collector`, StartInterval 14400, currently booted out during repair.
- Python: /opt/homebrew/bin/python3 (3.14.5). Do not assume compatible third-party packages without checking.
- Local repository directory: ~/Downloads/atlas-github-release (do not assume it is current or authoritative).

## Execution mandate
Work on actual installed source, not hypothetical APIs. Inspect relevant functions and call graph fully. Do not modify a running collector. If PID 7200 is still active, request/perform a graceful SIGINT or SIGTERM before any source change; confirm termination, check DB connections and preserve WAL. Avoid SIGKILL except escalation with evidence.

1. INVENTORY and baseline
   - Inspect app.py lines ~360-460 and all relevant TED network helpers, sync_engine.py, sync_daily.py and their imports; locate exact network call and pagination algorithm.
   - Identify why output remains empty until completion; identify current timeouts, retry policies, query strategy, maximum page window, transaction scope and source run logging.
   - Snapshot SHA256 of existing scripts and database count per source; confirm FTS5 and PRAGMA integrity_check on a separate copy or read-only where valid. Ensure no active connections before backup. Preserve original script versions.
   - Validate with actual runtime source files and configuration; do not infer behavior from grep alone.

2. PATCH TED NETWORK AND PAGINATION
   - Enforce bounded connect AND per-read timeouts. Crucially also enforce a total wall-clock budget per TED run; socket timeout alone is not sufficient if the server slowly streams bytes.
   - Timeouts are explicit, configurable, with documented safe defaults and limited retries with backoff+jitter respecting HTTP 429 Retry-After; never indefinitely retry.
   - Page iteration must be finite (maximum pages and deadline); detect repeated page signatures/IDs and repeated continuation cursor, and terminate with partial/error state rather than loop.
   - Parse remote HTTP errors, malformed JSON, short/empty responses; preserve raw diagnostics safely, avoid credentials.
   - Process and commit incrementally at bounded page/chunk boundaries; idempotent UPSERTs; do not make a whole TED harvest one transaction.
   - Preserve existing semantics of `opportunities`, FTS5 triggers, country normalization, bookmark and stage handling. NEVER drop/recreate the dataset.
   - Avoid forcing a full 105,200-notice scan on every 4-hour cycle. Implement delta query/window where supported by the actual TED API, and a separately controllable backfill. Verify API semantics with live documentation if needed; do not invent fields.
   - Distinguish `received`, `valid`, `inserted_unique`, `updated_existing`, `skipped`, `pages`, with stored last successful cursor/window and future safe resume. Do not equate processed rows to new rows.

3. OBSERVABILITY
   - Create atomic `~/AtlasMarches/data/sync-status.json` immediately with `state=running`, timestamps, current source, page, counts and source failures. Update after each page and at completion, with schema version.
   - Save process ID, last request time, last response time, most recent successful page, last error, retry count and `last_success_at`. No secrets or full raw payload.
   - Write line-oriented, flushed progress to log, so `tail -f` works while in progress. Make a JSON report for partial/completed/failed outcomes. Ensure interrupted process emits a final interrupted/partial state where possible.
   - Add interprocess lock, preventing overlapping manual+scheduled runs. Treat stale locks carefully.
   - Fatal exit status must be nonzero; partial success must be explicit (not misleading `ok`).

4. FTS5 CONSISTENCY
   - Investigate original inconsistency cause: trigger schema, FTS rebuild logic, concurrent writes, batch updates and connection management. Do not presume network wait caused FTS failure.
   - Add FTS5 integrity check in controlled maintenance/CI against copied DB, not inside every live transaction.
   - No automatic production rebuild when a check fails; fail safely and keep backups.

5. TESTS BEFORE RESUMING
   - Stub HTTP network to simulate: slow streaming, hanging reads, 429 Retry-After, 500, invalid JSON, duplicate page/cursor, empty page, transient failure, cancel between pages.
   - Run on a separate temporary SQLite DB with FTS5 enabled and synthetic notices. Test idempotency, incremental commits, counters, resume, lock, atomic status file, max time, and FTS5 integrity.
   - Verify on real source using a bounded small-page dry-run or staging DB first; NEVER use unbounded production fetch as a smoke test.
   - In live controlled run: require baseline counts, TED pages >0 and status success or partial with explicit reason; check DB count by source, `PRAGMA integrity_check`, FTS5 integrity on an appropriate safe copy and no data loss.

6. SEPARATE CONNECTORS
   - Record APProch and EU Funding/Grants existing parser failures explicitly, but do not silently mark them connected or successful. Implement adapters in a distinct follow-up lane after TED is stable, each with captured response fixture (scrub secrets) and tests. APProch project forecasts are not equivalent to live tenders.
   - `sources.json` catalog entries are not functioning ingestion sources; report both catalog count and confirmed ingesting connectors.

7. SCHEDULER / ACCEPTANCE GATE
   - Only reload `fr.atlasmarches.collector` AFTER validated bounded TED+BOAMP run, status file and reliable exit codes. Check launchctl print and schedule 14400; verify stdout and stderr paths; don't claim that `RunAtLoad` means success.
   - Document manual safe stop/start and independent collector health checks. Avoid permanently tying the collector to web UI.

## Mandatory return
Provide (a) exact source diff with file hashes, (b) evidence of tests with commands/outputs, (c) dry-run and first controlled collection metrics, (d) count by source before/after and FTS5/SQLite checks, (e) LaunchAgent state, (f) remaining blocked connectors and why, (g) explicit go/no-go for automated 4-hour collection. Don't report deployment as complete if only code was generated.

## Safety gates
- Database and backup files above are immutable until explicitly approved.
- Do not touch WAL/-shm manually.
- Avoid `kill -9`, deleting data, bulk reimport, forced index rebuild and unbounded requests.
- Any interrupted run may have partial committed pages: resume must be idempotent.
- Preserve existing web UI and established app paths.
