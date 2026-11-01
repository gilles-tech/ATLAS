"""Public European Commission Funding & Tenders search integration.

Data remains separate from TED/BOAMP procurement notices. No fake rows when
schema changes; a failed response is a visible failure, not a zero-result run.
"""
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError

ENDPOINT = 'https://api.tech.ec.europa.eu/search-api/prod/rest/search'
PORTAL = 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/'
KINDS = {'tenders': ['0'], 'grants': ['1','2','8']}
STATUSES = {'open': ['31094501','31094502'], 'all': ['31094501','31094502','31094503']}


def query_for(kind, status='open'):
    if kind not in KINDS or status not in STATUSES:
        raise ValueError('Catégorie ou statut non reconnu')
    return {'bool': {'must': [{'terms': {'type': KINDS[kind]}}, {'terms': {'status': STATUSES[status]}}]}}


def multipart(parts):
    boundary = 'atlas-' + uuid.uuid4().hex
    body = bytearray()
    for key, (value, mime) in parts.items():
        body.extend((f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\nContent-Type: {mime}\r\n\r\n{value}\r\n').encode())
    body.extend((f'--{boundary}--\r\n').encode())
    return bytes(body), f'multipart/form-data; boundary={boundary}'


def fetch_page(kind, status, page, page_size=100, opener=urlopen):
    params = urlencode({'apiKey': 'SEDIA', 'text': '*', 'pageSize': page_size,
                        'pageNumber': page, 'sortBy': 'es_SortDate', 'orderBy': 'DESC'})
    payload, content_type = multipart({
        'query': (json.dumps(query_for(kind, status)), 'application/json'),
        'languages': (json.dumps(['en']), 'application/json'),
        'displayLanguage': ('en', 'application/json'),
    })
    req = Request(ENDPOINT + '?' + params, data=payload, method='POST', headers={
        'Content-Type': content_type, 'Accept': 'application/json',
        'User-Agent': 'AtlasMarches/FT-1.0'})
    try:
        with opener(req, timeout=45) as reply:
            response = json.load(reply)
    except HTTPError as err:
        raise RuntimeError(f'EU FT HTTP {err.code}: {err.read(1600).decode("utf-8", "replace")}') from err
    if not isinstance(response, dict):
        raise ValueError('EU FT : la réponse doit être un objet JSON')
    # Current search API exposes results; alternate content wrappers are accepted only
    # when the structure is unambiguous.
    hits = response.get('results')
    if isinstance(hits, dict):
        hits = hits.get('results') or hits.get('items')
    if hits is None:
        hits = response.get('items')
    if hits is None and isinstance(response.get('data'), dict):
        hits = response['data'].get('results')
    if not isinstance(hits, list):
        raise ValueError('EU FT : format de résultats inconnu ; aucune écriture')
    return hits, response


def value(record, *keys):
    for key in keys:
        x = record.get(key)
        if isinstance(x, dict):
            x = x.get('en') or x.get('value') or x.get('label')
        if isinstance(x, list):
            x = next((v for v in x if isinstance(v, str) and v), None)
        if x is not None and str(x).strip():
            return str(x).strip()
    return ''


def documents(record):
    """Explicit supported wrappers from SEDIA results; never mistake an arbitrary
    plain-text excerpt for a structured title or identifier."""
    result=[record]
    for key in ('_source','source','metadata','enrichedMetadata'):
        entry=record.get(key)
        if isinstance(entry,dict):
            result.append(entry)
    content=record.get('content')
    if isinstance(content,str) and content.lstrip().startswith('{'):
        try:
            doc=json.loads(content)
            if isinstance(doc,dict):result.append(doc)
        except ValueError:
            pass
    return result


def structured_value(record,*keys):
    for doc in documents(record):
        direct=value(doc,*keys)
        if direct:return direct
        for container in ('metadata','enrichedMetadata'):
            nested=doc.get(container)
            if isinstance(nested,dict):
                candidate=value(nested,*keys)
                if candidate:return candidate
    return ''


def normalize(record, kind):
    if not isinstance(record,dict):return None
    identifier=structured_value(record,'identifier','topicIdentifier','callIdentifier',
                                'reference','topicId','id')
    title=structured_value(record,'title','topicTitle','name','callTitle','topicName')
    # An API result may supply a valid reference but only an unstructured summary.
    # Do not fabricate a title or silently count this as an imported opportunity.
    if not identifier or not title:return None
    url=structured_value(record,'url','portalUrl','link','topicUrl')
    if not url.startswith('https://'):
        url=PORTAL+identifier if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{3,199}',identifier) else ''
    if not url.startswith('https://'):return None
    return {'id':f'EU_FT_{kind.upper()}:{identifier}', 'kind':kind,
            'reference':identifier,'title':title,
            'summary':structured_value(record,'shortDescription','description','abstract'),
            'status_raw':structured_value(record,'status','statusCode'),
            'deadline':structured_value(record,'deadline','deadlineDate','submissionDeadline'),
            'published':structured_value(record,'publicationDate','openingDate','startDate'),
            'url':url,'raw':json.dumps(record,ensure_ascii=False)}


def install(db):
    db.execute('''CREATE TABLE IF NOT EXISTS eu_ft_calls (
         id TEXT PRIMARY KEY, kind TEXT NOT NULL, reference TEXT NOT NULL,
         title TEXT NOT NULL, summary TEXT, status_raw TEXT, deadline TEXT,
         published TEXT, url TEXT NOT NULL, retrieved TEXT NOT NULL, raw TEXT NOT NULL)''')
    db.execute('CREATE INDEX IF NOT EXISTS ix_euft_kind ON eu_ft_calls(kind)')


def collect(connect, kind='tenders', status='open', max_pages=None, fetcher=fetch_page):
    if max_pages is None:
        max_pages = int(os.getenv('ATLAS_EU_FT_PAGES','5'))
    if not 1 <= int(max_pages) <= 1000:
        raise ValueError('ATLAS_EU_FT_PAGES doit être compris entre 1 et 1000')
    total_received = total_valid = total_new = 0
    for page in range(1,int(max_pages)+1):
        for attempt in range(3):
            try:
                hits, response = fetcher(kind,status,page)
                break
            except (TimeoutError, OSError, RuntimeError) as err:
                if attempt == 2: raise
                time.sleep(2**attempt)
        total_received += len(hits)
        normalized = [x for r in hits if (x := normalize(r,kind))]
        if hits and not normalized:
            raise ValueError('EU FT : résultats reçus mais aucun identifiant/titre interprétable ; import arrêté')
        now=datetime.now(timezone.utc).isoformat()
        with connect() as db:
            install(db)
            for item in normalized:
                exists = db.execute('SELECT 1 FROM eu_ft_calls WHERE id=?',(item['id'],)).fetchone()
                db.execute('''INSERT INTO eu_ft_calls(id,kind,reference,title,summary,status_raw,deadline,published,url,retrieved,raw)
                    VALUES(:id,:kind,:reference,:title,:summary,:status_raw,:deadline,:published,:url,:retrieved,:raw)
                    ON CONFLICT(id) DO UPDATE SET title=excluded.title,summary=excluded.summary,
                    status_raw=excluded.status_raw,deadline=excluded.deadline,published=excluded.published,
                    url=excluded.url,retrieved=excluded.retrieved,raw=excluded.raw''',dict(item,retrieved=now))
                if not exists:total_new += 1
        total_valid += len(normalized)
        if len(hits) < 100: break
    return {'source':'EU_FT_'+kind.upper(),'status':'ok','count':total_valid,
            'received':total_received,'new':total_new,'category':kind,
            'note':'Appels d’offres et financements stockés séparément de TED/BOAMP'}
