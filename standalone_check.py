"""Smoke-test the built desktop runtime using only temporary data and loopback."""
import json
import os
from pathlib import Path
import platform
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen


class Fixture(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', '0')))
        body = b'{"notices":[]}'
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def run(report_path):
    import app
    from collector_runtime import atomic_json
    from maintenance import inspect_copy
    from ted_collector import bounded_http, settings_from_env
    report = {'status': 'running', 'platform': platform.system(), 'architecture': platform.machine()}
    previous_db = app.DB
    previous_proxy = {key: os.environ.get(key) for key in ('NO_PROXY', 'no_proxy')}
    try:
        import webview
        assert callable(webview.create_window)
        report['webview_import'] = 'ok'
        for name in ('static/index.html', 'sources.json', 'buyers.json', 'access_registry.json'):
            assert (app.ROOT/name).is_file(), 'Missing bundled asset: ' + name
        report['bundled_assets'] = 'ok'
        with tempfile.TemporaryDirectory(prefix='atlas-standalone-') as directory:
            app.DB = Path(directory)/'smoke.db'
            app.init()
            report['database'] = inspect_copy(app.DB)
            for key in previous_proxy:
                os.environ[key] = '127.0.0.1,localhost'
            server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
            fixture = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
            threads = []
            for service in (server, fixture):
                thread = threading.Thread(target=service.serve_forever, daemon=True)
                thread.start()
                threads.append(thread)
            try:
                base = f'http://127.0.0.1:{server.server_port}'
                with urlopen(base+'/', timeout=5) as response:
                    assert response.status == 200 and b'<html' in response.read().lower()
                with urlopen(base+'/api/stats', timeout=5) as response:
                    assert json.load(response)['records'] == 0
                report['ui_and_api'] = 'ok'
                cfg = settings_from_env()
                cfg.update(request_seconds=10, connect_seconds=5, read_seconds=5)
                result = bounded_http({}, time.monotonic()+15, threading.Event(), cfg,
                                      endpoint=f'http://127.0.0.1:{fixture.server_port}/')
                assert result == {'notices': []}
                report['bundled_worker_process'] = 'ok'
            finally:
                for service in (server, fixture):
                    service.shutdown()
                    service.server_close()
                for thread in threads:
                    thread.join()
        report['status'] = 'passed'
    except Exception as exc:
        report.update(status='failed', error=str(exc))
    finally:
        app.DB = previous_db
        for key, value in previous_proxy.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if report_path:
            atomic_json(report_path, report)
        print(json.dumps(report, indent=2), flush=True)
    return 0 if report['status'] == 'passed' else 1
