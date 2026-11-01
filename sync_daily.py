#!/usr/bin/env python3
"""Manual/launchd collection entrypoint. Shared locking is in sync_engine.run."""
import argparse
import json
from pathlib import Path
import sys


def main():
    import app
    from sync_engine import run
    parser = argparse.ArgumentParser()
    parser.add_argument('--include-optional', action='store_true',
                        help='Also try unvalidated APProch and EU Funding adapters')
    args = parser.parse_args()
    report = run(app, Path(app.DB).parent / 'sync-status.json', include_optional=args.include_optional)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if report['status'] == 'completed' else 2 if report['status'] == 'already_running' else 1


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(main())
