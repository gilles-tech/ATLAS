# Atlas Marchés

Public procurement discovery app and collector, based on the supplied Atlas
Collector installer and matching live-sync release. The TED recovery requirements
are implemented in this checkout; the UI and BOAMP adapter are preserved.

## Run the app

Requires Python 3 with SQLite FTS5; no third-party dependencies for the local UI.

```sh
cd /workspace/ATLAS
ATLAS_DB=/workspace/atlas-data/atlas.db python3 app.py --serve --port 8000
```

The server binds to loopback port 8000. The cloud database holds 94 APProch forecast
projects imported from the uploaded spreadsheet. These are future projects, not
confirmed open tenders. No production Mac database or backups were imported.
Keep the DB outside the checkout and preserve it between runs. The service has
no authentication; keep it local.

## Recovery, validation and builds

See [RECOVERY.md](RECOVERY.md) for bounded TED defaults, resume behavior, locking,
status files, safe stop/start, maintenance checks and deployment gates.

```sh
python3 -m unittest discover -p 'test_*.py' -v
python3 maintenance.py /workspace/atlas-data/atlas.db
python3 packaging/build_collector_installer.py
```

All 41 tests pass. The installer build produces
`release/Atlas-Collector-Recovery-v1-macOS-unsigned.zip`: an unsigned script-based
macOS installer requiring Python, not a bundled runtime or validated native DMG.
It installs files without activating collection or scheduling. The existing native
desktop build must run and be validated on macOS; it has not been built here.

Four-hour scheduling remains **NO-GO**: the single bounded live TED staging attempt
failed to connect and received zero pages. Live TED query semantics, BOAMP runtime
access and the original Mac's source/database/backup checks remain outstanding.
APProch and EU Funding remote adapters are deferred by default, not marked successful.
Do not activate legacy scheduling scripts while these gates are unresolved.

Source provenance is in `docs/installer-source-sha256.json` (original archive
hashes), `docs/additional-archives.json` (merge decisions), and
`docs/recovery-hashes.json` (recovered source hashes). Review the full diff and
concrete validation evidence in `docs/recovery.patch` and `docs/recovery-report.json`.
The historical recovery documents are retained under `docs/` as references; their
Mac process IDs and record counts have not been verified in this cloud environment.
