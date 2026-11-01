"""Check a consistent disposable copy; never rebuild or modify the source DB."""
import argparse
import json
from pathlib import Path
import sqlite3
import tempfile


def inspect_copy(database):
    source_path = Path(database).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    with tempfile.TemporaryDirectory(prefix='atlas-integrity-') as directory:
        source = sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True, timeout=5)
        copy = sqlite3.connect(str(Path(directory) / 'check.db'))
        try:
            source.backup(copy)
            integrity = [row[0] for row in copy.execute('PRAGMA integrity_check')]
            if integrity != ['ok']:
                raise RuntimeError('SQLite integrity failed: ' + repr(integrity[:5]))
            copy.execute("INSERT INTO opportunities_fts(opportunities_fts,rank) VALUES('integrity-check',1)")
            counts = dict(copy.execute('SELECT source,COUNT(*) FROM opportunities GROUP BY source'))
            return {'sqlite_integrity': 'ok', 'fts5_integrity': 'ok', 'by_source': counts,
                    'checked': 'consistent temporary backup; source opened read-only'}
        finally:
            source.close()
            copy.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database')
    args = parser.parse_args()
    try:
        print(json.dumps(inspect_copy(args.database), indent=2))
    except Exception as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}))
        raise SystemExit(1)
