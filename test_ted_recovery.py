"""Recovery gates: isolated fixtures and local HTTP only; no production DB."""
import contextlib
import io
import json
import multiprocessing
import signal
import subprocess
import sys
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import app
import ted_collector as ted
from collector_runtime import AlreadyRunning, atomic_json, run_lock
from maintenance import inspect_copy
from sync_engine import run


def notice(number='001', **extra):
    return {'publication-number': number, 'notice-title': 'Network services',
            'buyer-country': 'FRA', 'form-type': 'competition', **extra}


def hold_lock(database, ready, release):
    with run_lock(database):
        ready.set()
        release.wait(5)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = self.root / 'atlas.db'
        self.db_patch = patch.object(app, 'DB', self.database)
        self.db_patch.start()
        app.init()
        self.cfg = ted.settings_from_env()
        self.cfg.update(max_pages=3, page_size=3, total_seconds=5, retries=1)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()

    def tearDown(self):
        self.output.__exit__(None, None, None)
        self.db_patch.stop()
        self.temp.cleanup()

    def collect(self, fetcher, **kwargs):
        return ted.collect(app, settings=self.cfg, fetcher=fetcher, **kwargs)

    def count(self):
        with app.connect() as conn:
            return conn.execute('SELECT COUNT(*) FROM opportunities').fetchone()[0]

    def test_incremental_commit_counters_resume_and_idempotency(self):
        self.cfg['max_pages'] = 1
        first = self.collect(lambda *args: {'notices': [notice(), notice()], 'iterationNextToken': 'next'})
        self.assertEqual(first['state'], 'partial')
        self.assertEqual((first['received'], first['valid'], first['inserted_unique'], first['skipped']), (2, 2, 1, 1))
        self.assertEqual(self.count(), 1)
        self.assertIsNone(json.loads((self.root/'ted-checkpoint.json').read_text())['last_success_at'])
        def resume(body, *args):
            self.assertEqual(body['iterationNextToken'], 'next')
            self.assertEqual(self.count(), 1)  # Earlier page already committed.
            return {'notices': [notice('002')]}
        second = self.collect(resume)
        self.assertEqual(second['state'], 'completed')
        self.assertTrue(second['resumed'])
        self.assertEqual(self.count(), 2)
        repeat = self.collect(lambda *args: {'notices': [notice(), notice('002')]})
        self.assertEqual((repeat['inserted_unique'], repeat['updated_existing']), (0, 2))
        self.assertEqual(inspect_copy(self.database)['fts5_integrity'], 'ok')

    def test_crash_after_commit_before_checkpoint_replays_safely(self):
        original = ted.atomic_json
        def fail_checkpoint(path, value):
            if Path(path).name == 'ted-checkpoint.json' and value.get('pending', {}).get('token') == 'next':
                raise OSError('simulated crash saving checkpoint')
            return original(path, value)
        with patch.object(ted, 'atomic_json', side_effect=fail_checkpoint):
            result = self.collect(lambda *a: {'notices': [notice()], 'iterationNextToken': 'next'})
        self.assertEqual(result['state'], 'partial')
        self.assertEqual(self.count(), 1)
        result = self.collect(lambda *a: {'notices': [notice()]})
        self.assertEqual(result['updated_existing'], 1)
        self.assertEqual(self.count(), 1)

    def test_repeated_page_ids_are_partial(self):
        calls = []
        def fetch(*args):
            calls.append(1)
            return {'notices': [notice()], 'iterationNextToken': str(len(calls))}
        result = self.collect(fetch)
        self.assertEqual(result['state'], 'partial')
        self.assertIn('repeated page', result['last_error'])
        self.assertEqual((result['pages'], self.count()), (1, 1))

    def test_repeated_cursor_is_partial(self):
        pages = iter([{'notices': [notice()], 'iterationNextToken': 'same'},
                      {'notices': [notice('002')], 'iterationNextToken': 'same'}])
        result = self.collect(lambda *a: next(pages))
        self.assertEqual(result['state'], 'partial')
        self.assertIn('repeated continuation', result['last_error'])
        self.assertEqual(self.count(), 2)

    def test_empty_page_completes(self):
        result = self.collect(lambda *a: {'notices': []})
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(result['received'], 0)

    def test_bad_schema_does_not_become_zero_result_success(self):
        for payload in ({}, [], {'notices': [{}]}, {'notices': 'oops'}):
            with self.subTest(payload=payload):
                result = self.collect(lambda *a: payload, resume=False)
                self.assertEqual(result['state'], 'error')
        self.assertEqual(self.count(), 0)

    def test_transient_failure_then_success(self):
        replies = iter([ted.TransportError('500', True, '0'), {'notices': [notice()]}])
        def fetch(*args):
            result = next(replies)
            if isinstance(result, Exception): raise result
            return result
        result = self.collect(fetch)
        self.assertEqual((result['state'], result['retries']), ('completed', 1))

    def test_429_retry_after_exceeds_budget(self):
        def fetch(*args): raise ted.TransportError('429', True, '3600')
        started = time.monotonic()
        result = self.collect(fetch)
        self.assertEqual(result['state'], 'partial')
        self.assertIn('retry delay', result['last_error'])
        self.assertLess(time.monotonic()-started, 1)

    def test_retries_are_finite(self):
        calls = []
        def fetch(*args):
            calls.append(1)
            raise ted.TransportError('500', True, '0')
        result = self.collect(fetch)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result['state'], 'error')

    def test_cancel_between_pages_preserves_resume(self):
        cancel = threading.Event()
        def progress(state):
            if state['pages'] == 1: cancel.set()
        result = self.collect(lambda *a: {'notices': [notice()], 'iterationNextToken': 'next'},
                              cancel=cancel, progress=progress)
        self.assertEqual(result['state'], 'interrupted')
        self.assertEqual(self.count(), 1)
        self.assertEqual(json.loads((self.root/'ted-checkpoint.json').read_text())['pending']['token'], 'next')

    def test_deadline_before_commit_leaves_database_unchanged(self):
        self.cfg['total_seconds'] = .05
        def fetch(*args):
            time.sleep(.08)
            return {'notices': [notice()]}
        result = self.collect(fetch)
        self.assertEqual(result['state'], 'partial')
        self.assertEqual(self.count(), 0)

    def test_delta_and_backfill_queries_and_watermark(self):
        bodies = []
        def fetch(body, *args):
            bodies.append(body)
            return {'notices': []}
        result = self.collect(fetch)
        self.assertIn('publication-date >=', bodies[-1]['query'])
        prior_success = result['last_success_at']
        self.collect(fetch, backfill=True)
        self.assertEqual(bodies[-1]['query'], 'form-type = competition')
        self.assertTrue(prior_success)
        self.assertEqual(json.loads((self.root/'ted-checkpoint.json').read_text())['last_success_at'], prior_success)

    def test_invalid_unlimited_settings_are_rejected(self):
        for name, value in [('MAX_PAGES', '0'), ('RETRIES', '99'), ('TOTAL_SECONDS', 'NaN')]:
            with patch.dict(os.environ, {'ATLAS_TED_'+name: value}):
                with self.assertRaises(ValueError): ted.settings_from_env()

    def test_bookmarks_country_and_fts_survive_upserts(self):
        self.collect(lambda *a: {'notices': [notice()]})
        with app.connect() as c:
            c.execute("INSERT INTO bookmarks VALUES ('TED:001')")
        self.collect(lambda *a: {'notices': [notice(**{'buyer-country': ''})]})
        with app.connect() as c:
            self.assertEqual(c.execute("SELECT country FROM opportunities").fetchone()[0], 'FR')
            self.assertEqual(c.execute('SELECT COUNT(*) FROM bookmarks').fetchone()[0], 1)
        self.assertEqual(inspect_copy(self.database)['fts5_integrity'], 'ok')

    def test_fts_corruption_is_detected_and_not_rebuilt_on_startup(self):
        self.collect(lambda *a: {'notices': [notice()]})
        with app.connect() as c:
            c.execute("INSERT INTO opportunities_fts(opportunities_fts) VALUES('delete-all')")
        app.init()
        with self.assertRaises(sqlite3.DatabaseError):
            inspect_copy(self.database)
        self.assertEqual(self.count(), 1)

    def test_atomic_status_failed_replace_preserves_previous_and_cleans_temp(self):
        path = self.root/'status.json'
        atomic_json(path, {'state': 'old'})
        with patch('collector_runtime.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): atomic_json(path, {'state': 'new'})
        self.assertEqual(json.loads(path.read_text()), {'state': 'old'})
        self.assertEqual(list(self.root.glob('status.json.*')), [])

    def test_interprocess_lock_and_kernel_release(self):
        ctx = multiprocessing.get_context('spawn')
        ready, release = ctx.Event(), ctx.Event()
        worker = ctx.Process(target=hold_lock, args=(str(self.database), ready, release))
        worker.start()
        try:
            self.assertTrue(ready.wait(4))
            with self.assertRaises(AlreadyRunning):
                with run_lock(self.database): pass
            result = self.collect(lambda *a: self.fail('Network called while locked'))
            self.assertEqual(result['state'], 'already_running')
            with patch.object(app, 'boamp_fetch', side_effect=AssertionError('network called')):
                self.assertEqual(app.ingest('BOAMP')['status'], 'already_running')
        finally:
            release.set()
            worker.join(4)
            if worker.is_alive(): worker.terminate(); worker.join()
            worker.close()
        with run_lock(self.database): pass  # PID file remains; kernel lock released.

    def test_sync_status_exists_before_init_failure(self):
        from types import SimpleNamespace
        path = self.root/'sync-status.json'
        def init():
            self.assertEqual(json.loads(path.read_text())['state'], 'running')
            raise RuntimeError('broken schema')
        fake = SimpleNamespace(DB=self.database, SOURCES=[], init=init)
        result = run(fake, path)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('broken schema', result['last_error'])

    def test_page_progress_updates_aggregate_status(self):
        path = self.root/'sync-status.json'
        def fetch(*args):
            current = json.loads(path.read_text())
            self.assertEqual(current['current_source'], 'TED')
            self.assertIsNotNone(current['last_request_at'])
            return {'notices': [notice()]}
        original = app.run_ted_full
        with patch.object(app, 'ingest', return_value={'status': 'ok', 'count': 0}), \
             patch.object(app, 'run_ted_full', side_effect=lambda **kwargs: original(fetcher=fetch, settings=self.cfg, **kwargs)):
            result = run(app, path)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['sources']['TED']['result']['inserted_unique'], 1)
        self.assertEqual(result['sources']['TED']['result']['pages'], 1)
        self.assertIn('APPROCH', result['deferred_sources'])

    def test_bounded_boamp_ted_fixture_run_and_integrity(self):
        original = app.run_ted_full
        payload = {'results': [{'idweb': 'B001', 'objet': 'Public network', 'nomacheteur': 'City',
                                'datelimitereponse': '2027-01-20'}]}
        with patch.object(app, 'read_json', return_value=payload), \
             patch.object(app, 'run_ted_full', side_effect=lambda **kw: original(
                 settings=self.cfg, fetcher=lambda *a: {'notices': [notice()]}, **kw)):
            result = run(app, self.root/'sync-status.json')
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['delta_by_source'], {'BOAMP': 1, 'TED': 1})
        with app.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM runs WHERE status='ok'").fetchone()[0], 2)
        self.assertEqual(inspect_copy(self.database)['by_source'], {'BOAMP': 1, 'TED': 1})

    def test_cli_exit_codes(self):
        import sync_daily
        for status, code in [('completed', 0), ('partial_error', 1), ('already_running', 2), ('interrupted', 1)]:
            with patch('sync_engine.run', return_value={'status': status}), patch.object(sys, 'argv', ['sync_daily.py']):
                self.assertEqual(sync_daily.main(), code)

    def test_sigterm_publishes_final_interrupted_state(self):
        script = '''import app,time
app.init()
app.run_ted_full(fetcher=lambda *a: (time.sleep(20) or {'notices':[]}))
'''
        environment = dict(os.environ, ATLAS_DB=str(self.database))
        worker = subprocess.Popen([sys.executable, '-c', script], cwd=Path(__file__).parent,
                                  env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        path = self.root/'ted-status.json'
        try:
            limit = time.monotonic()+4
            while time.monotonic()<limit:
                if path.exists() and json.loads(path.read_text()).get('last_request_at'): break
                time.sleep(.02)
            else: self.fail('Child did not start request')
            worker.send_signal(signal.SIGTERM)
            _, stderr = worker.communicate(timeout=3)
            self.assertEqual(json.loads(path.read_text())['state'], 'interrupted', stderr.decode())
            with run_lock(self.database): pass
        finally:
            if worker.poll() is None: worker.terminate(); worker.communicate(timeout=3)


class LocalHTTP(BaseHTTPRequestHandler):
    mode = 'valid'

    def log_message(self, *args): pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', '0')))
        if self.mode in ('429', '500'):
            self.send_response(int(self.mode)); self.send_header('Retry-After', '2'); self.end_headers(); return
        self.send_response(200)
        if self.mode == 'stream': self.send_header('Content-Length', '1000000')
        self.end_headers()
        if self.mode == 'hang':
            time.sleep(2); return
        if self.mode == 'stream':
            try:
                for _ in range(100):
                    self.wfile.write(b' '); self.wfile.flush(); time.sleep(.03)
            except (BrokenPipeError, ConnectionResetError): pass
            return
        data = {'valid': b'{"notices":[]}', 'invalid': b'{bad', 'empty': b'', 'large': b'x'*500}
        self.wfile.write(data[self.mode])


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), LocalHTTP)
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def fetch(self, mode, budget=1):
        LocalHTTP.mode = mode
        cfg = ted.settings_from_env()
        cfg.update(request_seconds=budget, read_seconds=.3, connect_seconds=.3, max_bytes=100)
        with patch.dict(os.environ, {'NO_PROXY': '127.0.0.1', 'no_proxy': '127.0.0.1'}):
            return ted.bounded_http({}, time.monotonic()+budget, threading.Event(), cfg,
                                    endpoint=f'http://127.0.0.1:{self.server.server_port}/')

    def test_valid_json(self):
        self.assertEqual(self.fetch('valid'), {'notices': []})

    def test_malformed_empty_and_oversize_responses(self):
        for mode in ('invalid', 'empty', 'large'):
            with self.subTest(mode=mode), self.assertRaises(ted.TransportError) as exc:
                self.fetch(mode)
            self.assertFalse(exc.exception.retryable)

    def test_http_retry_after_and_500(self):
        for mode in ('429', '500'):
            with self.subTest(mode=mode), self.assertRaises(ted.TransportError) as exc:
                self.fetch(mode)
            self.assertTrue(exc.exception.retryable)
            self.assertEqual(exc.exception.retry_after, '2')

    def test_slow_stream_and_hanging_read_are_bounded(self):
        for mode in ('stream', 'hang'):
            started = time.monotonic()
            with self.subTest(mode=mode), self.assertRaises(ted.TransportError):
                self.fetch(mode, budget=.6)
            self.assertLess(time.monotonic()-started, 1.5)
        self.assertFalse(multiprocessing.active_children())


if __name__ == '__main__': unittest.main()
