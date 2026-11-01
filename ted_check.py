"""One bounded TED staging run; never writes the configured application DB."""
import argparse
import json
import os
from pathlib import Path
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='atlas-ted-check-') as directory:
        os.environ['ATLAS_DB'] = str(Path(directory)/'staging.db')
        import app
        from maintenance import inspect_copy
        from ted_collector import settings_from_env
        app.init()
        settings = settings_from_env()
        settings.update(max_pages=1, page_size=2, total_seconds=20, request_seconds=15,
                        retries=0, connect_seconds=5, read_seconds=5)
        before = inspect_copy(app.DB)
        result = app.run_ted_full(settings=settings, resume=False)
        after = inspect_copy(app.DB)
        report = {'before': before, 'result': result, 'after': after,
                  'production_database_touched': False}
        from collector_runtime import atomic_json
        atomic_json(args.report, report)
        print(json.dumps(report, indent=2), flush=True)
        return 0 if result['state']=='completed' else 1


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    raise SystemExit(main())
