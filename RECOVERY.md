# TED collector recovery

The uploaded installer is the source baseline. These changes implement the
launcher’s recovery requirements on that source; they have not been installed
on the original Mac. The production database, backups and PID 7200 described
in the reference documents are not available in this Linux environment.

## Behavior

- All TED collection entrypoints use the same bounded collector. The old
  `--ted-all-open` option remains as a compatibility alias for the routine delta
  run; use `--ted-backfill` explicitly for the bounded ACTIVE competition backfill.
- Default routine query: competition notices published since the last completed
  window, overlapping two days. First run uses 14 days. A partial run retains
  its exact query and continuation token, and never advances the success watermark.
  Delta and backfill have separate checkpoints.
- The query fields, publication-date syntax, ACTIVE scope and iteration token
  protocol come from the uploaded source. Their current live API semantics have
  not been validated here because the single staging request failed to connect.
  The publication window cannot detect changes to arbitrarily old notices:
  use a separately controlled backfill when that coverage is required.
- Each HTTP attempt runs in a disposable subprocess. Parent-enforced deadlines
  stop a hanging/slow stream and close its socket. urllib uses the stricter of
  the configured connect/read limits for both socket operations. TLS validation
  and inherited proxy/CA configuration remain enabled.
- Retryable transport errors, HTTP 429 and 500/502/503/504 have finite retries.
  Retry-After seconds and HTTP dates are respected; a delay beyond the remaining
  budget returns partial instead of retrying early. Error bodies are not read.
  Malformed JSON diagnostics include byte count and SHA256, never raw payloads.
- Every page is committed by idempotent UPSERT before its checkpoint advances.
  A crash between commit and checkpoint safely replays that page. Bookmarks and
  existing country-preservation semantics are retained. Counters distinguish
  received, valid, inserted_unique, updated_existing and skipped. updated_existing
  counts upserted existing records, including identical records; it is not a
  count of changed business fields. Duplicate IDs within one page count as skipped.
- Repeated ID-page signatures or cursor cycles produce partial/error outcomes.
  A repeated cursor is retained for inspection rather than discarded as success.
  If an API cursor expires, inspect the failure and use `--ted-no-resume` to replay
  the unchanged delta window from its beginning; UPSERTs prevent duplicates.
- Shared kernel locks cover manual TED, web ingestion, desktop sync and scheduled
  sync against the same resolved DB. Never remove a lock file to break a lock.
  Process exit releases it; an old PID in an unlocked file does not block a run.
- Status JSON uses unique temporary files, fsync and atomic replacement. It is
  written before network work and after each page, alongside flushed JSON log lines.
  SIGINT/SIGTERM produce interrupted status and preserve committed pages.
- APProch and EU Funding/Grants are deferred by default, with explicit unrun status.
  `sync_daily.py --include-optional` is for their separate diagnostic lane; parser
  failures propagate, never become successful empty imports.

## Configuration

All names below have prefix `ATLAS_TED_`:

| Suffix | Default | Meaning |
| --- | ---: | --- |
| TOTAL_SECONDS | 180 | Total TED collection budget |
| REQUEST_SECONDS | 30 | Wall-clock budget per HTTP attempt |
| CONNECT_SECONDS | 10 | Maximum socket connect timeout |
| READ_SECONDS | 10 | Maximum socket read timeout |
| MAX_PAGES | 20 | Finite pages per invocation; zero is rejected |
| PAGE_SIZE | 100 | Rows requested per page; maximum 100 |
| RETRIES | 2 | Additional attempts; maximum 5 |
| MAX_BYTES | 8000000 | Response byte cap |
| OVERLAP_DAYS | 2 | Completed delta-window overlap |
| INITIAL_DAYS | 14 | Initial delta lookback |

State is beside the selected `ATLAS_DB`: `sync-status.json`, `ted-status.json`,
`ted-checkpoint.json`, `ted-backfill-checkpoint.json` and `atlas.db.collector.lock`.
Checkpoints contain opaque API continuation tokens; keep them local with the DB.
Do not copy checkpoint data into public reports.

## Validation and manual operation

From the repository or installed collector directory, with collectors stopped:

```sh
python3 -m unittest discover -p 'test_*.py' -v
python3 maintenance.py /path/to/atlas.db
```

Maintenance opens the selected source read-only, takes a consistent SQLite backup
into a temporary directory, and runs SQLite and FTS5 rank=1 integrity checks only
on that copy. It never rebuilds an index or touches WAL/-shm manually. Production
backups and the original Mac's integrity must still be verified before deployment.

The former external-content FTS count comparison could not detect index corruption.
Startup no longer rebuilds automatically. Tests demonstrate that corrupted postings
are detected on a copy and are not silently repaired by restart. This does not prove
the historical cause of corruption on the Mac; that requires its trigger schema,
write paths and database. Existing data without an FTS index now fails explicitly
and requires a separate, approved maintenance procedure.

For one bounded LIVE staging request after network access is applied:

```sh
python3 ted_check.py --report /path/outside/repo/ted-live-check.json
```

This command uses a disposable DB, one page of two rows, no retries, a 20-second
total budget and a 15-second request budget. It never changes production data.
A page cap with a continuation token is a truthful partial outcome (nonzero exit).
The staging script is a live check, not an offline dry-run.

After staging and backups are verified, manual core synchronization is:

```sh
ATLAS_DB=/path/to/approved/database python3 sync_daily.py
```

Stop the exact PID reported in status gracefully with SIGINT or SIGTERM, then wait
for exit and verify final status. Do not signal a historical PID without verifying
its command and start time. Do not use kill -9 or delete WAL/-shm. UI and collector
are separate processes; the UI is not needed by `sync_daily.py`.

Exit codes: sync CLI 0=completed, 1=failed/partial/interrupted, 2=lock already held.
`app.py --ted-all-open` and `--ted-backfill` use the same outcome codes.

## Build and deployment gate

`python3 packaging/build_collector_installer.py` builds an unsigned script-based
macOS installer ZIP. It requires an existing Python 3 installation on the Mac.
Its dialogs accurately state that no collection is started. The installer refuses
to replace a loaded collector or a detected running collector process, copies the
new runtime modules, and leaves the four-hour LaunchAgent unloaded with RunAtLoad
false. It does not modify the user's database. It is not a self-contained native
runtime, a signed/notarized DMG, or a macOS-validated binary.

The existing `packaging/build_macos_release.sh` builds the native desktop app/DMG
on macOS with its optional build dependencies. That build cannot be executed on
this Linux host and remains unverified. No Actions workflow was dispatched.

**NO-GO for four-hour scheduled operation.** The full 41-test suite and isolated
BOAMP+TED fixture run pass; a live staging attempt received zero pages and failed
to connect. The current restricted policy omits required hosts. Draft additions
are `api.ted.europa.eu`, `boamp-datadila.opendatasoft.com`, `docs.ted.europa.eu`.
Saving a draft does not apply those changes or validate API semantics.

Before activation: confirm the actual installed source matches the reviewed patch;
stop/verify the real Mac process; confirm and preserve the named backups; record
counts by source; pass bounded live TED+BOAMP collection and copied integrity
checks; inspect status, exit codes and log paths. Only then load the reviewed
`fr.atlasmarches.collector` plist and verify `launchctl print` reports interval
14400 with correct stdout/stderr paths. No scheduler activation occurred here.

The cloud DB remains 94 APProch forecast projects, TED=0 and BOAMP=0. There are
83 catalog entries, zero enabled feeds and no remotely verified connectors in
this cloud session. Manual spreadsheet import is verified; remote APProch,
EU_FT_TENDERS and EU_FT_GRANTS parsing remains a separate unverified lane.

See `docs/recovery-report.json`, `docs/recovery-tests.txt`,
`docs/recovery.patch` and `docs/recovery-hashes.json` for the exact evidence.
