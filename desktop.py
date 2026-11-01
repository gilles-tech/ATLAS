"""Cross-platform Atlas desktop entrypoint, bundled with PyInstaller.
Run without arguments for GUI, --sync for unattended synchronization.
"""
import argparse
import json
import os
import socket
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from http.server import ThreadingHTTPServer

import app

DATA = Path.home() / 'AtlasMarches' / 'data'
DATA.mkdir(parents=True, exist_ok=True)
STATUS = DATA / 'desktop-sync-status.json'

def sync():
    from sync_engine import run
    report = run(app, Path(app.DB).parent / 'sync-status.json', include_optional=True)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if report['status'] in ('completed','continuation_pending') else 2 if report['status']=='already_running' else 1

def available_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sync', action='store_true')
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.self_check:
        from standalone_check import run
        return run(args.report)
    if args.sync: return sync()
    app.init()
    port = available_port()
    http = ThreadingHTTPServer(('127.0.0.1',port), app.Handler)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    try:
        import webview
        webview.create_window('Atlas Marchés', f'http://127.0.0.1:{port}/index.html', width=1400, height=920, min_size=(940, 620))
        # The installed collector LaunchAgent owns recurring updates. Never create a second scheduler.
        webview.start()
    finally:
        http.shutdown()
        http.server_close()
    return 0

if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(main())
