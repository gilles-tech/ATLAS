#!/usr/bin/env python3
"""Mac-only guarded ATLAS collector source rollout. NEVER starts collection."""
import argparse, datetime, hashlib, json, os, shutil, sqlite3, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = Path.home() / "AtlasMarches/data/atlas.db"
TARGET = Path.home() / "Library/Application Support/AtlasMarches/collector"
FILES = ("app.py", "sync_daily.py", "sync_engine.py", "collector_runtime.py",
         "ted_collector.py", "maintenance.py", "ted_check.py", "approch.py",
         "eu_ft.py", "sources.json", "buyers.json", "access_registry.json",
         "RECOVERY.md")

def stop(message):
    raise SystemExit("STOP: " + message)

def command(*args):
    return subprocess.run(args, capture_output=True, text=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    opt = parser.parse_args()
    if sys.platform != "darwin": stop("Run only on user's macOS")
    if not DB.is_file() or not TARGET.is_dir(): stop("Installed Mac DB/collector missing")
    git = command("git", "-C", str(ROOT), "status", "--porcelain")
    if git.returncode or git.stdout.strip(): stop("Checkout must be clean")
    if any(not (ROOT/name).is_file() for name in FILES): stop("Missing source files")
    label = f"gui/{os.getuid()}/fr.atlasmarches.collector"
    if command("launchctl", "print", label).returncode == 0:
        stop("Unload collector LaunchAgent deliberately first")
    ps = command("ps", "-axo", "pid=,command=")
    if ps.returncode: stop("Cannot inspect processes")
    for line in ps.stdout.splitlines():
        if any(x in line for x in ("sync_daily.py", "run-collector.sh", "app.py --port", "AtlasMarches.app/Contents/MacOS")):
            stop("An Atlas process is still running: " + line)
    paths = [str(p) for p in (DB, Path(str(DB)+"-wal"), Path(str(DB)+"-shm")) if p.exists()]
    lsof = command("lsof", "-n", "-P", *paths)
    if lsof.returncode != 1: stop("SQLite open or lsof error: " + lsof.stdout + lsof.stderr)
    with sqlite3.connect(DB.resolve().as_uri()+"?mode=ro", uri=True, timeout=10) as source:
        counts = dict(source.execute("SELECT source,COUNT(*) FROM opportunities GROUP BY source"))
        count = sum(counts.values())
        if count < 108346: stop("Below verified 108346-notice baseline")
        print("Source counts", counts)
        if not opt.apply:
            print("PREFLIGHT PASS: no writes; rerun with --apply to install code only")
            return
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = Path.home() / "AtlasMarches/backups" / ("rollout-"+stamp)
        backup.mkdir(parents=True, exist_ok=False)
        with sqlite3.connect(backup/"atlas.db") as dest: source.backup(dest)
    with sqlite3.connect((backup/"atlas.db").resolve().as_uri()+"?mode=ro", uri=True) as check:
        if check.execute("PRAGMA integrity_check").fetchone()[0]!="ok": stop("Backup integrity failed")
        if check.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]!=count:
            stop("Backup count mismatch")
    # SQLite integrity_check does not validate FTS5 external-content postings.
    with sqlite3.connect(backup/"atlas.db") as fts:
        try:
            fts.execute("INSERT INTO opportunities_fts(opportunities_fts,rank) VALUES ('integrity-check',1)")
        except sqlite3.DatabaseError as exc:
            stop("FTS5 consistency failed on backup: " + str(exc))
    previous = backup/"prior-code"
    previous.mkdir()
    for name in FILES:
        current = TARGET/name
        if current.exists(): shutil.copy2(current, previous/name)
    for name in FILES:
        staging = TARGET/("."+name+".rollout")
        try:
            shutil.copy2(ROOT/name, staging)
            if hashlib.sha256(staging.read_bytes()).digest()!=hashlib.sha256((ROOT/name).read_bytes()).digest():
                stop("Staging checksum mismatch: "+name)
            os.replace(staging, TARGET/name)
        finally:
            staging.unlink(missing_ok=True)
    print("SOURCE DEPLOYED — database unchanged; scheduler NOT started")
    print("Backup: "+str(backup))
    print("Next: bounded staging TED then controlled live acceptance; only then reload launchd")

if __name__ == "__main__":
    main()
