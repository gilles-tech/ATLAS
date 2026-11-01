"""Shared synchronization with durable page progress and truthful outcomes."""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import sqlite3
import threading
import time
from collector_runtime import AlreadyRunning, atomic_json, interruptible, run_lock


def utc():
    return datetime.now(timezone.utc).isoformat()


def snapshot(db):
    if not Path(db).is_file():
        return {'total': 0, 'by_source': {}, 'latest_retrieved': None}
    conn = sqlite3.connect('file:' + str(Path(db).resolve()) + '?mode=ro', uri=True, timeout=5)
    try:
        sources = dict(conn.execute('SELECT source, COUNT(*) FROM opportunities GROUP BY source'))
        latest = conn.execute('SELECT MAX(retrieved) FROM opportunities').fetchone()[0]
        return {'total': sum(sources.values()), 'by_source': sources, 'latest_retrieved': latest}
    finally:
        conn.close()


def run(app, state_file, include_feeds=True, include_optional=False, cancel=None):
    cancel = cancel or threading.Event()
    try:
        with run_lock(app.DB), interruptible(cancel):
            return _run(app, Path(state_file), include_feeds, include_optional, cancel)
    except AlreadyRunning as exc:
        # Do not overwrite the active owner's status file.
        return {'status': 'already_running', 'state': 'already_running', 'error': str(exc)}


def _run(app, state_file, include_feeds, include_optional, cancel):
    state = dict(schema_version=1, started=utc(), finished=None, status='running', state='running',
                 pid=os.getpid(), database=str(app.DB), current_source=None, page=0,
                 sources={}, source_failures={}, catalog_count=len(app.SOURCES),
                 enabled_feeds=[], notes=[], continuations={}, last_success_at=None)
    # Carry a successful full-run timestamp, never infer success from the clock alone.
    if state_file.exists():
        try:
            prior = json.loads(state_file.read_text(encoding='utf-8'))
            state['last_success_at'] = prior.get('last_success_at')
        except (OSError, ValueError):
            state['notes'].append('Previous status unreadable; retained separately by the operator if needed.')

    def store():
        atomic_json(state_file, state)
        print(json.dumps({'event': 'sync_progress', **state}, ensure_ascii=False), flush=True)

    def ted_progress(report):
        state['page'] = report['pages']
        for key in ('received', 'valid', 'inserted_unique', 'updated_existing', 'skipped',
                    'retries', 'last_request_at', 'last_response_at', 'most_recent_successful_page', 'last_error'):
            state[key] = report.get(key)
        state['sources']['TED'] = dict(status=report['state'], result=report)
        store()

    before = None
    store()  # Must exist even when initialization fails.
    try:
        app.init()
        before = snapshot(app.DB)
        state['before'] = before
        # Supplied fake adapters used by tests may not expose callback parameters.
        if hasattr(app, 'collection_guard'):
            ted = lambda: app.run_ted_full(progress=ted_progress, cancel=cancel)
        else:
            ted = app.run_ted_full
        sources = [('BOAMP', lambda: app.ingest('BOAMP')), ('TED', ted)]
        optional = [('APPROCH', lambda: app.ingest('APPROCH')),
                    ('EU_FT_TENDERS', lambda: app.eu_ft_ingest('tenders')),
                    ('EU_FT_GRANTS', lambda: app.eu_ft_ingest('grants'))]
        if include_optional:
            sources += optional
        else:
            state['deferred_sources'] = [name for name, _ in optional]
            state['notes'].append('APProch and EU Funding adapters deferred to a separate validation lane; not marked successful.')
        if include_feeds:
            feeds = [f['id'] for f in app.feed_registry() if f.get('enabled') and f.get('id')]
            state['enabled_feeds'] = feeds
            sources += [(name, lambda name=name: app.ingest(name)) for name in feeds]
            if not feeds:
                state['notes'].append('Aucun flux RSS/Atom supplémentaire activé : feeds.json est vide ou désactivé.')
        for name, call in sources:
            if cancel.is_set():
                raise KeyboardInterrupt
            state['current_source'], state['page'] = name, 0
            store()
            started = time.monotonic()
            try:
                result = call()
                if not isinstance(result, dict):
                    raise ValueError('Unstructured collector result')
                outcome = result.get('status') or result.get('state') or 'unknown'
                state['sources'][name] = dict(status=outcome,
                    duration_seconds=round(time.monotonic()-started, 3), result=result)
                expected_ted_checkpoint = (
                    name == 'TED' and outcome == 'partial'
                    and result.get('last_error') == 'TED page limit reached; continuation checkpoint saved'
                    and result.get('pages', 0) > 0
                )
                if expected_ted_checkpoint:
                    state['continuations'][name] = {
                        'status': 'checkpoint_saved', 'pages': result['pages'],
                        'received': result.get('received', 0)
                    }
                elif outcome not in ('ok', 'completed'):
                    state['status'] = 'partial_error'
                    state['source_failures'][name] = result.get('last_error') or result.get('error') or result.get('message') or outcome
                if outcome == 'interrupted':
                    cancel.set()
                    raise KeyboardInterrupt
            except Exception as exc:
                state['status'] = 'partial_error'
                state['source_failures'][name] = str(exc)[:500]
                state['sources'][name] = dict(status='error', error=str(exc)[:500])
            state['progress_snapshot'] = snapshot(app.DB)
            store()
        if state['status'] == 'running':
            if state['continuations']:
                state['status'] = 'continuation_pending'
            else:
                state['status'] = 'completed'
                state['last_success_at'] = utc()
    except (KeyboardInterrupt, SystemExit):
        state['status'] = 'interrupted'
        state['last_error'] = 'Collection interrupted; committed pages remain resumable'
    except Exception as exc:
        state['status'] = 'failed'
        state['last_error'] = str(exc)[:500]
    finally:
        state['finished'] = utc()
        state['state'] = state['status']
        try:
            state['after'] = after = snapshot(app.DB)
            if before is not None:
                state['new_unique_records'] = after['total'] - before['total']
                state['delta_by_source'] = {source: after['by_source'].get(source, 0)-before['by_source'].get(source, 0)
                                          for source in set(before['by_source']) | set(after['by_source'])}
        except Exception as exc:
            state['snapshot_error'] = str(exc)[:300]
            if state['status'] == 'completed':
                state['status'] = state['state'] = 'failed'
        store()
    return state
