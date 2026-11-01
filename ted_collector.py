"""Bounded TED transport and recoverable, incremental collection.

The endpoint, query fields and iteration protocol come from the supplied app.
Every HTTP attempt runs in a disposable process so a slow TLS stream cannot
outlive the request/run deadline. No detached reader threads accumulate.
"""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import random
import tempfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from collector_runtime import AlreadyRunning, atomic_json, run_lock, interruptible

ENDPOINT = 'https://api.ted.europa.eu/v3/notices/search'
FIELDS = ['publication-number', 'publication-date', 'notice-title', 'buyer-name',
          'buyer-country', 'classification-cpv', 'deadline-receipt-tender-date-lot',
          'form-type', 'notice-type']


def utc():
    return datetime.now(timezone.utc).isoformat()


class CollectionStopped(RuntimeError):
    pass


class TransportError(RuntimeError):
    def __init__(self, message, retryable=False, retry_after=None):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


def _http_worker(endpoint, body, timeout, maximum, target):
    """Child owns the socket; killing this child closes even a stalled read."""
    try:
        request = Request(endpoint, data=json.dumps(body).encode(), method='POST',
                          headers={'Content-Type': 'application/json',
                                   'Accept': 'application/json',
                                   'User-Agent': 'AtlasMarches/TED-recovery-1'})
        with urlopen(request, timeout=timeout) as response:
            data = response.read(maximum + 1)
            if len(data) > maximum:
                raise ValueError('TED response exceeds byte limit')
            if not data:
                raise ValueError('TED returned an empty response body')
            try:
                payload = json.loads(data)
            except (ValueError, UnicodeError) as exc:
                raise ValueError('TED returned malformed JSON; bytes=' + str(len(data)) +
                                 '; sha256=' + hashlib.sha256(data).hexdigest()) from exc
            result = {'payload': payload}
    except HTTPError as exc:
        # Do not read an error body: it too may stream forever, or contain secrets.
        result = {'error': 'TED HTTP ' + str(exc.code), 'retryable': exc.code in
                  (429, 500, 502, 503, 504), 'retry_after': exc.headers.get('Retry-After')}
    except (URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, 'reason', exc)
        description = str(reason)
        category = ('proxy policy/tunnel denied' if '403' in description else
                    'TLS certificate verification failed' if 'CERTIFICATE_VERIFY_FAILED' in description else
                    'connection refused' if 'Connection refused' in description else
                    type(reason).__name__)
        # Classify without exposing proxy URLs, headers, credentials or payloads.
        result = {'error': 'TED connection/read failed: ' + category,
                  'retryable': category not in ('proxy policy/tunnel denied', 'TLS certificate verification failed')}
    except Exception as exc:
        result = {'error': str(exc) if isinstance(exc, ValueError) else type(exc).__name__,
                  'retryable': False}
    Path(target).write_text(json.dumps(result), encoding='utf-8')


def bounded_http(body, deadline, cancel, settings, endpoint=ENDPOINT):
    remaining = min(deadline - time.monotonic(), settings['request_seconds'])
    if remaining <= 0:
        raise CollectionStopped('TED total deadline reached')
    # urllib uses one socket timeout for connect and reads; use the stricter cap.
    socket_timeout = min(settings['connect_seconds'], settings['read_seconds'], remaining)
    context = multiprocessing.get_context('spawn')
    with tempfile.TemporaryDirectory(prefix='atlas-ted-http-') as directory:
        target = str(Path(directory) / 'response.json')
        worker = context.Process(target=_http_worker, args=(endpoint, body, socket_timeout,
                                 settings['max_bytes'], target), daemon=True)
        try:
            worker.start()
            attempt_deadline = time.monotonic() + remaining
            while worker.is_alive():
                if cancel.is_set():
                    raise CollectionStopped('TED interrupted')
                if time.monotonic() >= min(deadline, attempt_deadline):
                    raise TransportError('TED request wall-clock timeout', retryable=True)
                worker.join(min(.05, max(0, min(deadline, attempt_deadline)-time.monotonic())))
            if not Path(target).exists():
                raise TransportError('TED HTTP worker failed', retryable=False)
            result = json.loads(Path(target).read_text(encoding='utf-8'))
            if 'error' in result:
                raise TransportError(result['error'], result.get('retryable', False),
                                     result.get('retry_after'))
            return result['payload']
        finally:
            if worker.pid is not None and worker.is_alive():
                worker.terminate()
                worker.join(1)
                if worker.is_alive():
                    worker.kill()  # Only our disposable HTTP child, never a collector.
                    worker.join(1)
            worker.close()


def settings_from_env():
    defaults = {'total_seconds': 180, 'request_seconds': 30, 'connect_seconds': 10,
                'read_seconds': 10, 'max_pages': 20, 'page_size': 100, 'retries': 2,
                'max_bytes': 8_000_000, 'overlap_days': 2, 'initial_days': 14}
    for key, default in list(defaults.items()):
        value = float(os.getenv('ATLAS_TED_' + key.upper(), str(default)))
        if key in ('max_pages', 'page_size', 'retries', 'max_bytes', 'overlap_days', 'initial_days'):
            if not value.is_integer():
                raise ValueError('TED integer setting required: ' + key)
            value = int(value)
        if not math.isfinite(value) or value < 0 or (key != 'retries' and value == 0):
            raise ValueError('Invalid TED setting: ' + key)
        defaults[key] = value
    if defaults['max_pages'] > 1000 or defaults['page_size'] > 100 or defaults['retries'] > 5:
        raise ValueError('TED maximum: 1000 pages, 100 rows/page, 5 retries')
    return defaults


def retry_delay(value, attempt):
    if value is not None:
        try:
            delay = float(value)
        except ValueError:
            try:
                delay = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                delay = 0
        if math.isfinite(delay):
            return max(0, delay)
    return min(8, 2 ** attempt) + random.uniform(0, .25)


def normalize(app, notice):
    if not isinstance(notice, dict):
        return None
    number = app.ted_scalar(notice.get('publication-number') or notice.get('publicationNumber'))
    if not number:
        return None
    form = app.ted_scalar(notice.get('form-type')).lower()
    if 'award' in form or 'result' in form:
        return None
    deadline = app.normalized_date(app.ted_scalar(notice.get('deadline-receipt-tender-date-lot')))
    today = datetime.now(timezone.utc).date().isoformat()
    return dict(id='TED:' + number, source='TED',
                title=app.ted_scalar(notice.get('notice-title')) or 'Avis TED ' + number,
                description='', kind=app.ted_scalar(notice.get('notice-type') or notice.get('form-type')) or 'AUTRE',
                country=app.ted_country(notice), region='', buyer=app.ted_scalar(notice.get('buyer-name')),
                cpv=app.ted_scalar(notice.get('classification-cpv')), value=None, currency='EUR',
                published=app.normalized_date(app.ted_scalar(notice.get('publication-date'))),
                deadline=deadline, url='https://ted.europa.eu/fr/notice/-/detail/' + number,
                stage='expired' if deadline and deadline[:10] < today else 'tender' if deadline else 'unknown',
                raw=notice)


def collect(app, *, settings=None, fetcher=None, cancel=None, progress=None,
            backfill=False, resume=True, state_dir=None):
    settings = settings or settings_from_env()
    cancel = cancel or threading.Event()
    fetcher = fetcher or bounded_http
    directory = Path(state_dir or Path(app.DB).parent)
    status_file = directory / 'ted-status.json'
    checkpoint_file = directory / ('ted-backfill-checkpoint.json' if backfill else 'ted-checkpoint.json')
    try:
        with run_lock(app.DB), interruptible(cancel):
            return _collect(app, settings, fetcher, cancel, progress, backfill, resume,
                            status_file, checkpoint_file)
    except AlreadyRunning:
        return {'state': 'already_running', 'error': 'A collector already owns this database'}


def _collect(app, cfg, fetcher, cancel, progress, backfill, resume, status_file, checkpoint_file):
    started = time.monotonic()
    deadline = started + cfg['total_seconds']
    state = dict(schema_version=1, source='TED', state='running', pid=os.getpid(), started=utc(),
                 finished=None, mode='backfill' if backfill else 'delta', pages=0, received=0,
                 valid=0, inserted_unique=0, updated_existing=0, skipped=0, saved=0,
                 retries=0, last_request_at=None, last_response_at=None,
                 most_recent_successful_page=None, last_error=None, last_success_at=None, total=None)
    checkpoint = {}

    def publish():
        atomic_json(status_file, state)
        print(json.dumps({'event': 'ted_progress', **state}, ensure_ascii=False), flush=True)
        if progress:
            progress(dict(state))

    def check():
        if cancel.is_set():
            raise CollectionStopped('TED interrupted')
        if time.monotonic() >= deadline:
            raise CollectionStopped('TED total deadline reached')

    publish()  # A running status exists before checkpoint, DB or network work.
    try:
        if checkpoint_file.exists():
            checkpoint = json.loads(checkpoint_file.read_text(encoding='utf-8'))
            if checkpoint.get('schema_version') != 1:
                raise ValueError('Unsupported TED checkpoint schema; inspect before resuming')
        mode = state['mode']
        watermark = checkpoint.get('last_success_at')
        state['last_success_at'] = watermark
        lower = (datetime.fromisoformat(watermark) - timedelta(days=cfg['overlap_days'])
                 if watermark else datetime.now(timezone.utc) - timedelta(days=cfg['initial_days']))
        query = 'form-type = competition'
        if not backfill:
            query += ' AND publication-date >= ' + lower.strftime('%Y%m%d')
        pending = checkpoint.get('pending') if resume else None
        if pending and pending.get('mode') == mode:
            query = pending['query']
            token = pending.get('token')
            window_started = pending['window_started']
            seen_tokens = set(pending.get('seen_tokens', []))
            seen_signatures = set(pending.get('seen_signatures', []))
        else:
            token, seen_tokens, seen_signatures = None, set(), set()
            window_started = state['started']
        state['query'] = query
        state['resumed'] = bool(pending and pending.get('mode') == mode)
        checkpoint = {'schema_version': 1, 'last_success_at': watermark, 'pending':
                      dict(mode=mode, query=query, token=token, window_started=window_started,
                           seen_tokens=sorted(seen_tokens), seen_signatures=sorted(seen_signatures))}
        atomic_json(checkpoint_file, checkpoint)
        for page in range(1, cfg['max_pages'] + 1):
            check()
            body = dict(query=query, fields=FIELDS, limit=cfg['page_size'], scope='ACTIVE',
                        paginationMode='ITERATION', checkQuerySyntax=False)
            if token:
                body['iterationNextToken'] = token
            for attempt in range(cfg['retries'] + 1):
                check()
                state['last_request_at'] = utc()
                publish()
                try:
                    payload = fetcher(body, deadline, cancel, cfg)
                    state['last_response_at'] = utc()
                    check()
                    break
                except TransportError as exc:
                    if str(exc).startswith('TED HTTP '):
                        state['last_response_at'] = utc()
                    state['last_error'] = str(exc)
                    if not exc.retryable or attempt == cfg['retries']:
                        raise
                    delay = retry_delay(exc.retry_after, attempt)
                    if time.monotonic() + delay >= deadline:
                        raise CollectionStopped('TED retry delay exceeds remaining deadline') from exc
                    state['retries'] += 1
                    publish()
                    if cancel.wait(delay):
                        raise CollectionStopped('TED interrupted during retry')
            if not isinstance(payload, dict):
                raise ValueError('TED response must be a JSON object')
            notices = payload.get('notices', payload.get('results'))
            if not isinstance(notices, list):
                raise ValueError('TED response has no notices list')
            if len(notices) > cfg['page_size']:
                raise ValueError('TED response exceeds requested page size')
            state['total'] = payload.get('totalNoticeCount')
            state['received'] += len(notices)
            rows = [row for notice in notices if (row := normalize(app, notice))]
            state['valid'] += len(rows)
            state['skipped'] += len(notices) - len(rows)
            if notices and not rows:
                raise ValueError('TED page contains no valid notice identifiers')
            signature = hashlib.sha256(json.dumps(sorted(row['id'] for row in rows)).encode()).hexdigest()
            if rows and signature in seen_signatures:
                raise CollectionStopped('TED repeated page IDs; cursor retained for inspection')
            next_token = payload.get('iterationNextToken')
            if next_token is not None and not isinstance(next_token, str):
                raise ValueError('TED continuation token must be a string')
            check()
            # One transaction per page. Counters and checkpoint advance only after commit.
            counts = app.save_batch(rows, detailed=True, deadline=deadline)
            for key in ('inserted_unique', 'updated_existing', 'skipped'):
                state[key] += counts[key]
            state['saved'] = state['inserted_unique'] + state['updated_existing']
            state['pages'] += 1
            state['most_recent_successful_page'] = state['pages']
            if rows:
                seen_signatures.add(signature)
            if token:
                seen_tokens.add(token)
            if next_token and (next_token == token or next_token in seen_tokens):
                publish()
                raise CollectionStopped('TED repeated continuation token; page committed, safe to replay')
            if not notices or not next_token:
                state['state'] = 'completed'
                state['last_success_at'] = window_started
                checkpoint = {'schema_version': 1, 'last_success_at': window_started, 'pending': None}
                atomic_json(checkpoint_file, checkpoint)
                break
            token = next_token
            checkpoint['pending'] = dict(mode=mode, query=query, token=token,
                                         window_started=window_started, seen_tokens=sorted(seen_tokens),
                                         seen_signatures=sorted(seen_signatures))
            atomic_json(checkpoint_file, checkpoint)
            publish()
        else:
            raise CollectionStopped('TED page limit reached; continuation checkpoint saved')
    except (KeyboardInterrupt, SystemExit):
        state['state'] = 'interrupted'
        state['last_error'] = 'TED interrupted by signal'
    except CollectionStopped as exc:
        state['state'] = 'interrupted' if cancel.is_set() else 'partial'
        state['last_error'] = str(exc)
    except Exception as exc:
        state['state'] = 'partial' if state['pages'] else 'error'
        state['last_error'] = str(exc)[:500]
    finally:
        connection = None
        try:
            connection = app.connect()
            connection.execute('PRAGMA busy_timeout=' + str(int(max(0, min(1, deadline-time.monotonic()))*1000)))
            with connection:
                connection.execute('INSERT INTO runs VALUES (?,?,?,?,?)',
                                   ('TED', utc(), 'ok' if state['state']=='completed' else state['state'],
                                    state['saved'], json.dumps({key: state.get(key) for key in
                                    ('pages', 'inserted_unique', 'updated_existing', 'skipped', 'last_error')})))
        except Exception as exc:
            state['run_log_error'] = type(exc).__name__
            if state['state'] == 'completed':
                state['state'] = 'partial'
                state['last_error'] = 'TED pages committed but run log could not be persisted'
        finally:
            if connection is not None:
                connection.close()
        state['finished'] = utc()
        state['elapsed_seconds'] = round(time.monotonic() - started, 3)
        state['error'] = state['last_error'] or ''
        publish()
    return state
