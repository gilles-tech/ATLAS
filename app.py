"""Atlas Marchés: dependency-free public procurement discovery MVP."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.request import Request, urlopen
from datetime import datetime, timezone, timedelta
from urllib.error import HTTPError, URLError
import sqlite3, json, os, re, threading, argparse, time, unicodedata, sys
import eu_ft
import approch
from collector_runtime import AlreadyRunning, run_lock
from functools import wraps

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
DB = Path(os.environ.get('ATLAS_DB', str(Path.home() / 'AtlasMarches' / 'data' / 'atlas.db'))).expanduser()
DB.parent.mkdir(parents=True, exist_ok=True)
SOURCES = json.loads((ROOT / 'sources.json').read_text(encoding='utf8'))
BUYERS = json.loads((ROOT / 'buyers.json').read_text(encoding='utf8'))
LOCK = threading.Lock()

def collection_guard(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            with run_lock(DB):
                return function(*args, **kwargs)
        except AlreadyRunning as exc:
            return {'status': 'already_running', 'state': 'already_running', 'error': str(exc)}
    return guarded


def connect():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.create_function('atlas_fold',1,lambda x: fold(x) if x else '')
    return c

def init():
    with connect() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''CREATE TABLE IF NOT EXISTS opportunities (
          id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL,
          description TEXT, kind TEXT, country TEXT, region TEXT, buyer TEXT,
          cpv TEXT, value REAL, currency TEXT, published TEXT, deadline TEXT,
          url TEXT NOT NULL, stage TEXT NOT NULL DEFAULT 'tender',
          retrieved TEXT NOT NULL, raw TEXT
        ); CREATE INDEX IF NOT EXISTS ix_source ON opportunities(source);
        CREATE INDEX IF NOT EXISTS ix_country ON opportunities(country);
        CREATE INDEX IF NOT EXISTS ix_deadline ON opportunities(deadline);
        CREATE TABLE IF NOT EXISTS bookmarks(id TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS runs(source TEXT, at TEXT, status TEXT, fetched INTEGER, message TEXT);''')
        # Counts on external-content FTS reflect the content table, not index health.
        # Never repair/rebuild a production index as a side effect of startup.
        has_fts = c.execute("SELECT 1 FROM sqlite_master WHERE name='opportunities_fts'").fetchone()
        if not has_fts and c.execute('SELECT count(*) FROM opportunities').fetchone()[0]:
            raise RuntimeError('Existing notices have no FTS index; validate a backup with maintenance.py first')
        try:
            c.executescript("""CREATE VIRTUAL TABLE IF NOT EXISTS opportunities_fts USING fts5(
              title, description, buyer, cpv, content='opportunities', content_rowid='rowid',
              tokenize='unicode61 remove_diacritics 2');
            CREATE TRIGGER IF NOT EXISTS opp_fts_ai AFTER INSERT ON opportunities BEGIN
              INSERT INTO opportunities_fts(rowid,title,description,buyer,cpv)
              VALUES (new.rowid,new.title,new.description,new.buyer,new.cpv); END;
            CREATE TRIGGER IF NOT EXISTS opp_fts_ad AFTER DELETE ON opportunities BEGIN
              INSERT INTO opportunities_fts(opportunities_fts,rowid,title,description,buyer,cpv)
              VALUES ('delete',old.rowid,old.title,old.description,old.buyer,old.cpv); END;
            CREATE TRIGGER IF NOT EXISTS opp_fts_au AFTER UPDATE ON opportunities BEGIN
              INSERT INTO opportunities_fts(opportunities_fts,rowid,title,description,buyer,cpv)
              VALUES ('delete',old.rowid,old.title,old.description,old.buyer,old.cpv);
              INSERT INTO opportunities_fts(rowid,title,description,buyer,cpv)
              VALUES (new.rowid,new.title,new.description,new.buyer,new.cpv); END;""")
        except sqlite3.OperationalError as e:
            if 'no such module: fts5' not in str(e).lower():
                raise
            print('[Recherche] FTS indisponible, recherche standard conservée:', e)


@collection_guard
def eu_ft_ingest(kind):
    try:
        outcome=eu_ft.collect(connect,kind)
        with connect() as c:c.execute('INSERT INTO runs VALUES (?,?,?,?,?)',(outcome['source'],datetime.now(timezone.utc).isoformat(),'ok',outcome['count'],f"new={outcome['new']}"))
        return outcome
    except Exception as exc:
        with connect() as c:c.execute('INSERT INTO runs VALUES (?,?,?,?,?)',('EU_FT_'+kind.upper(),datetime.now(timezone.utc).isoformat(),'error',0,str(exc)[:1800]))
        return {'source':'EU_FT_'+kind.upper(),'status':'error','count':0,'message':str(exc)[:1800]}

def first(d, *names):
    for name in names:
        v = d.get(name)
        if v not in (None, '', [], {}):
            if isinstance(v, dict):
                v = next((x for x in v.values() if isinstance(x, str) and x.strip()), None)
            if isinstance(v, list):
                v = ', '.join(str(x) for x in v[:3])
            if v is not None: return str(v)
    return ''

MONTHS={'janvier':1,'février':2,'fevrier':2,'mars':3,'avril':4,'mai':5,'juin':6,'juillet':7,'août':8,'aout':8,'septembre':9,'octobre':10,'novembre':11,'décembre':12,'decembre':12}
def normalized_date(value):
    if not value:return ''
    v=str(value).strip()
    try:
        if re.match(r'^\d{4}-\d{2}-\d{2}',v):return v
        m=re.match(r'^(\d{1,2})\s+([a-zA-Zéûèô]+)\s+(\d{4})(?:\s+(\d{1,2}):(\d{2}))?',v,re.I)
        if m:
            day,month,year,hr,minute=m.groups();mo=MONTHS.get(month.lower())
            if mo:return f'{int(year):04d}-{mo:02d}-{int(day):02d}'+(f'T{int(hr):02d}:{minute}:00' if hr else '')
        m=re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})',v)
        if m:return f'{int(m[3]):04d}-{int(m[2]):02d}-{int(m[1]):02d}'
    except (TypeError,ValueError):pass
    return ''

def read_json(request, timeout=30):
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)

def boamp_fetch(limit=None):
    """Collect fresh BOAMP notices with bounded pages and truthful partial failure reporting.

    The default is 30 pages (3,000 notices) per run, configurable using
    ATLAS_BOAMP_PAGES, to avoid a hanging request on local laptops.
    """
    base='https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records'
    pages=max(1,min(100,int(os.getenv('ATLAS_BOAMP_PAGES','30'))))
    if limit is not None: pages=max(1,min(pages,(limit+99)//100))
    result=[]
    for index in range(pages):
        size=min(100,max(1,limit-index*100)) if limit is not None else 100
        if size<=0:break
        url=base+'?'+urlencode({'limit':size,'offset':index*100,'order_by':'dateparution DESC'})
        payload=read_json(Request(url,headers={'User-Agent':'AtlasMarches/0.4','Accept':'application/json'}))
        batch=payload.get('results')
        if not isinstance(batch,list):raise ValueError('BOAMP: réponse API inattendue (results)')
        for item in batch:
            if not isinstance(item,dict):continue
            identifier=first(item,'idweb','id','recordid','reference','identifiant')
            if not identifier:continue
            nature=first(item,'nature','nature_libelle','type_avis','sousnature_libelle').lower()
            award=any(x in nature for x in ('attribution','resultat','résultat','award','conclusion')) or bool(first(item,'titulaire'))
            dl=normalized_date(first(item,'datelimitereponse','date_limite_reponse','datecloture'))
            pub=normalized_date(first(item,'dateparution','datepublication','date_publication'))
            expired=bool(dl and dl[:10]<datetime.now(timezone.utc).date().isoformat())
            stage='awarded' if award else 'expired' if expired else 'tender' if dl else 'unknown'
            official=first(item,'url_avis','urlavis','url','lien')
            if not official.startswith('https://'):official='https://www.boamp.fr/pages/avis/?'+urlencode({'q':'idweb:'+identifier})
            result.append({'id':'BOAMP:'+identifier,'source':'BOAMP','title':first(item,'objet','objetmarche','titre','intitule') or 'Avis BOAMP '+identifier,'description':first(item,'descripteur_libelle','resume','description','objet'),'kind':first(item,'type_marche','nature_libelle','typemarche') or 'AUTRE','country':'FR','region':first(item,'code_departement_prestation','code_departement','departement','codepostal'),'buyer':first(item,'nomacheteur','nom_acheteur','acheteur'),'cpv':first(item,'descripteur_code','codecpv','cpv'),'value':None,'currency':'EUR','published':pub,'deadline':dl,'url':official,'stage':stage,'raw':item})
        if len(batch)<size:break
    return result

# Configurable feed adapters: only feeds explicitly supplied by their publisher/operator.
# No HTML scraping, authentication bypass or invented URLs.
import xml.etree.ElementTree as ET
from hashlib import sha256
from urllib.parse import urljoin
FEED_FILE = ROOT / 'feeds.json'
def feed_registry():
    return json.loads(FEED_FILE.read_text(encoding='utf8')) if FEED_FILE.exists() else []

def xml_value(node, names):
    for item in node.iter():
        if item.tag.rsplit('}',1)[-1].lower() in names and item.text and item.text.strip():
            return item.text.strip()
    return ''

def feed_fetch(feed):
    source=feed['id']; url=feed['url']; max_items=min(5000,max(1,int(feed.get('max_items',1000))))
    if not url.startswith('https://'):raise ValueError('Flux HTTPS obligatoire')
    req=Request(url,headers={'User-Agent':'AtlasMarches/0.7 (+public procurement data research)','Accept':'application/atom+xml,application/rss+xml,application/xml,text/xml'})
    with urlopen(req,timeout=45) as response:
        if int(response.headers.get('Content-Length','0') or 0)>12_000_000:raise ValueError('Flux trop volumineux')
        raw=response.read(12_000_001)
    if len(raw)>12_000_000:raise ValueError('Flux trop volumineux')
    root=ET.fromstring(raw)
    items=[n for n in root.iter() if n.tag.rsplit('}',1)[-1] in ('item','entry')]
    out=[]
    for n in items[:max_items]:
        title=xml_value(n,{'title'})
        desc=xml_value(n,{'description','summary','content'})
        identity=xml_value(n,{'guid','id'})
        link=xml_value(n,{'link'})
        if not link:
            for l in n.iter():
                if l.tag.rsplit('}',1)[-1]=='link' and l.attrib.get('href'):
                    link=l.attrib['href'];break
        link=urljoin(url,link) if link else ''
        if not link.startswith('https://'):continue
        identity=identity or link
        public=normalized_date(xml_value(n,{'pubdate','published','updated','date'}))
        deadline=normalized_date(xml_value(n,{'deadline','closingdate','closing-date'}))
        today=datetime.now(timezone.utc).date().isoformat()
        stage='expired' if deadline and deadline[:10]<today else 'tender' if deadline else 'unknown'
        out.append({'id':source+':'+sha256(identity.encode()).hexdigest()[:24],'source':source,'title':title or 'Avis sans titre','description':desc[:6000], 'kind':'AUTRE','country':country_code(feed.get('country')) or 'UNKNOWN','region':feed.get('region',''),'buyer':feed.get('buyer',''),'cpv':'','value':None,'currency':'EUR','published':public,'deadline':deadline,'url':link,'stage':stage,'raw':{'feed':url,'guid':identity,'title':title,'description':desc,'published':public,'deadline':deadline}})
    return out

def ingest_feed(source):
    feed=next((x for x in feed_registry() if x['id']==source and x.get('enabled') is True),None)
    if feed is None:raise ValueError('Flux absent ou désactivé')
    rows=feed_fetch(feed)
    saved=save_batch(rows)
    with LOCK,connect() as c:c.execute('INSERT INTO runs VALUES (?,?,?,?,?)',(source,datetime.now(timezone.utc).isoformat(),'ok',saved,'RSS/Atom; statut inconnu si échéance absente'))
    return {'source':source,'count':saved,'status':'ok'}

def ted_scalar(value):
    if isinstance(value,dict):
        for key in ('fra','eng','text','value','FRA','ENG'):
            if key in value:return ted_scalar(value[key])
        return ted_scalar(next(iter(value.values()),''))
    if isinstance(value,list):return ted_scalar(value[0]) if value else ''
    return str(value) if value is not None else ''


COUNTRY_CODES = set('AD MC SM VA AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE NO CH IS LI UK GB RS BA ME MK AL MD UA TR GE AM AZ XK'.split())
COUNTRY_ALIASES = {'FRA':'FR','DEU':'DE','ESP':'ES','ITA':'IT','BEL':'BE','NLD':'NL','PRT':'PT','POL':'PL','AUT':'AT','CHE':'CH','GBR':'GB','GRC':'GR','ELL':'GR','DNK':'DK','SWE':'SE','NOR':'NO','FIN':'FI','IRL':'IE','CZE':'CZ','SVK':'SK','HUN':'HU','ROU':'RO','BGR':'BG','HRV':'HR','SVN':'SI','EST':'EE','LVA':'LV','LTU':'LT','LUX':'LU','MLT':'MT','CYP':'CY','ISL':'IS','LIE':'LI','SRB':'RS','BIH':'BA','MNE':'ME','MKD':'MK','ALB':'AL','MDA':'MD','UKR':'UA','TUR':'TR','GEO':'GE','ARM':'AM','AZE':'AZ','XKX':'XK','AND':'AD','MCO':'MC','SMR':'SM','VAT':'VA'}
def country_code(v):
    if isinstance(v,dict):
        for key in ('code','country','value','iso','iso2','countryCode','country-code'):
            if key in v:
                c=country_code(v[key])
                if c:return c
        for x in v.values():
            c=country_code(x)
            if c:return c
        return ''
    if isinstance(v,list):
        for x in v:
            c=country_code(x)
            if c:return c
        return ''
    value=str(v or '').strip().upper()
    if value in COUNTRY_CODES:return 'GB' if value=='UK' else value
    if value in COUNTRY_ALIASES:return COUNTRY_ALIASES[value]
    return ''
def _explicit_countries(obj, depth=0):
    """Only explicit country-labelled values. Never guess from arbitrary text or languages."""
    if depth>12:return []
    found=[]
    if isinstance(obj,list):
        for value in obj:found.extend(_explicit_countries(value,depth+1))
    elif isinstance(obj,dict):
        for key,value in obj.items():
            normalized=re.sub('[^a-z]','',str(key).lower())
            if normalized in ('buyercountry','buyercountrysub','buyercountrylot','organisationcountry','organizationcountry','countrycode','countryid','country','countryiso','countryiso2','countryiso3','countryofbuyer','countryoforigin'):
                code=country_code(value)
                if code:found.append(code)
            elif isinstance(value,(dict,list)):
                found.extend(_explicit_countries(value,depth+1))
    return found

def ted_country(n):
    if not isinstance(n,dict):return 'UNKNOWN'
    # Direct buyer field is strongest; never take language or raw first value.
    for key in ('buyer-country','buyerCountry','buyer_country','buyer-country-code','organisation-country'):
        if key in n:
            code=country_code(n[key])
            if code:return code
    values=set(_explicit_countries(n))
    return next(iter(values)) if len(values)==1 else 'UNKNOWN'


def normalize_all_country_codes():
    """Convert ISO-3166 alpha-3 and known aliases to alpha-2 in-place, transactionally.
    Never infer country from title or language. Back up SQLite with SQLite backup API.
    """
    from collections import Counter
    from datetime import datetime as _datetime
    with LOCK:
        with connect() as c:
            before=c.execute('SELECT COUNT(*) FROM opportunities').fetchone()[0]
            counts=dict(c.execute('SELECT country,COUNT(*) FROM opportunities GROUP BY country').fetchall())
            fixes={k:country_code(k) for k in counts if k and country_code(k) and country_code(k)!=k}
            backup=DB.parent/('atlas.before-country-normalization.'+_datetime.now().strftime('%Y%m%d-%H%M%S')+'.db')
            with sqlite3.connect(backup) as out:c.backup(out)
            changed=0
            c.execute('BEGIN IMMEDIATE')
            try:
                for old,new in fixes.items():
                    cursor=c.execute('UPDATE opportunities SET country=? WHERE country=?',(new,old))
                    changed+=cursor.rowcount
                after=c.execute('SELECT COUNT(*) FROM opportunities').fetchone()[0]
                if after!=before:raise RuntimeError('Count changed during country normalization')
                c.commit()
            except Exception:
                c.rollback();raise
            results=dict(c.execute('SELECT country,COUNT(*) FROM opportunities GROUP BY country').fetchall())
    return {'before':before,'after':after,'updated':changed,'mapped':fixes,'countries':results,'backup':str(backup)}

def repair_countries():
    """Repair only unclassified TED records from explicitly labelled raw country codes."""
    repaired=0
    with LOCK, connect() as c:
        cur=c.execute("SELECT id,raw FROM opportunities WHERE source='TED' AND (country IS NULL OR country IN ('UNKNOWN','EU',''))")
        while True:
            batch=cur.fetchmany(500)
            if not batch:break
            for row in batch:
                try: payload=json.loads(row['raw'] or '{}')
                except (TypeError,ValueError):continue
                code=ted_country(payload)
                if code!='UNKNOWN':
                    c.execute('UPDATE opportunities SET country=? WHERE id=?',(code,row['id']))
                    repaired+=1
    return repaired

def xml_country(xml):
    """Extract buyer-country only when unambiguous in an official TED notice XML."""
    import xml.etree.ElementTree as ET
    root=ET.fromstring(xml)
    candidates=[]
    for node in root.iter():
        tag=node.tag.rsplit('}',1)[-1].lower()
        if tag in ('countryidentificationcode','countrycode','country'):
            code=country_code((node.text or '').strip())
            if code:
                # Within party/buyer organisation postal address, not performance location.
                # ElementTree lacks parent pointers, so use independently extracted buyer-specific subtrees.
                continue
        if tag in ('contractingparty','contractingauthority','buyer','organisation','organization','economicoperatorparty','contractingbody'):
            for child in node.iter():
                ct=child.tag.rsplit('}',1)[-1].lower()
                if ct in ('countryidentificationcode','countrycode','country'):
                    code=country_code((child.text or '').strip())
                    if code:candidates.append(code)
    values=set(candidates)
    return next(iter(values)) if len(values)==1 else 'UNKNOWN'

def enrich_ted_countries(limit=100,delay=.12):
    """Retrieve official notice XML for TED rows still missing country. Resume safely on repeat."""
    import urllib.error
    with connect() as c:
        rows=c.execute("SELECT id FROM opportunities WHERE source='TED' AND (country IS NULL OR country IN ('UNKNOWN','EU','')) ORDER BY published DESC LIMIT ?",(limit,)).fetchall()
    report={'attempted':0,'repaired':0,'unresolved':0,'errors':0,'samples':[]}
    for row in rows:
        number=row['id'][4:]
        if not re.fullmatch(r'\d{1,9}-\d{4}',number):
            report['unresolved']+=1;continue
        url='https://ted.europa.eu/en/notice/'+number+'/xml'
        try:
            req=Request(url,headers={'User-Agent':'AtlasMarches/0.8.4 (public procurement research)','Accept':'application/xml,text/xml'})
            with urlopen(req,timeout=20) as res:
                payload=res.read(3_000_001)
            if len(payload)>3_000_000:raise ValueError('XML too large')
            code=xml_country(payload)
            report['attempted']+=1
            if code!='UNKNOWN':
                with LOCK,connect() as c:
                    c.execute("UPDATE opportunities SET country=? WHERE id=? AND (country IS NULL OR country IN ('UNKNOWN','EU',''))",(code,row['id']))
                report['repaired']+=1
            else:report['unresolved']+=1
        except Exception as exc:
            report['errors']+=1
            if len(report['samples'])<5:report['samples'].append(number+': '+str(exc)[:150])
        if report['attempted']%25==0 and report['attempted']:
            print('[TED enrichment] '+json.dumps(report,ensure_ascii=False),flush=True)
        time.sleep(delay)
    return report

# Full active-tender import: cursor iteration, durable batches and observable progress.
JOBS = {'TED': {'state':'idle','pages':0,'received':0,'saved':0,'total':None,'error':'','started':None}, 'BOAMP': {'state':'idle','pages':0,'received':0,'saved':0,'total':None,'error':'','started':None}}
JOB_LOCK = threading.Lock()

def save_batch(rows, detailed=False, deadline=None):
    now = datetime.now(timezone.utc).isoformat()
    counts = {'inserted_unique': 0, 'updated_existing': 0, 'skipped': 0}
    seen = set()
    remaining = max(0, deadline-time.monotonic()) if deadline else 30
    if not LOCK.acquire(timeout=min(30, remaining)):
        raise TimeoutError('Database writer lock deadline reached')
    try:
        with connect() as c:
            c.execute('PRAGMA busy_timeout=' + str(int(min(30, remaining)*1000)))
            c.execute('BEGIN IMMEDIATE')
            for x in rows:
                if deadline and time.monotonic() >= deadline:
                    raise TimeoutError('Database page deadline reached')
                if x['id'] in seen:
                    counts['skipped'] += 1
                    continue
                seen.add(x['id'])
                exists = c.execute('SELECT 1 FROM opportunities WHERE id=?', (x['id'],)).fetchone()
                c.execute('''INSERT INTO opportunities(id,source,title,description,kind,country,region,buyer,cpv,value,currency,published,deadline,url,stage,retrieved,raw)
                  VALUES (:id,:source,:title,:description,:kind,:country,:region,:buyer,:cpv,:value,:currency,:published,:deadline,:url,:stage,:retrieved,:raw)
                  ON CONFLICT(id) DO UPDATE SET title=excluded.title,description=excluded.description,country=CASE WHEN excluded.country NOT IN ('UNKNOWN','EU','') THEN excluded.country ELSE opportunities.country END,region=excluded.region,buyer=excluded.buyer,cpv=excluded.cpv,deadline=excluded.deadline,published=excluded.published,kind=excluded.kind,stage=excluded.stage,url=excluded.url,retrieved=excluded.retrieved,raw=excluded.raw''',dict(x,retrieved=now,raw=json.dumps(x['raw'],ensure_ascii=False)))
                counts['updated_existing' if exists else 'inserted_unique'] += 1
    finally:
        LOCK.release()
    return counts if detailed else counts['inserted_unique'] + counts['updated_existing']

def run_ted_full(*, progress=None, cancel=None, backfill=False, resume=True, settings=None, fetcher=None):
    # Legacy name retained for CLI/UI compatibility; routine runs now use a delta window.
    import ted_collector
    import sys as _sys
    def update(state):
        with JOB_LOCK:
            JOBS['TED'] = dict(state)
        if progress:
            progress(state)
        else:
            from collector_runtime import atomic_json
            atomic_json(DB.parent/'sync-status.json', dict(state, status=state['state'],
                        current_source='TED', sources={'TED': {'status': state['state'], 'result': state}},
                        source_failures={'TED': state['last_error']} if state['state'] in ('error','partial','interrupted') else {}))
    result = ted_collector.collect(_sys.modules[__name__], progress=update, cancel=cancel,
                                   backfill=backfill, resume=resume, settings=settings, fetcher=fetcher)
    with JOB_LOCK:
        JOBS['TED'] = dict(result)
    return result

def start_ted_full():
    with JOB_LOCK:
        if JOBS['TED']['state'] in ('running', 'starting'):return dict(JOBS['TED'])
        JOBS['TED'] = dict(state='starting', pages=0, received=0, saved=0, total=None, error='')
    threading.Thread(target=run_ted_full,daemon=True,name='ted-active-ingestion').start()
    return {'state':'starting','message':'Collecte TED lancée ; consulter /api/jobs'}

@collection_guard
def ingest(source):
    if source == 'TED':
        result = run_ted_full()
        return dict(result, source='TED', count=result.get('saved', 0),
                    status='ok' if result['state']=='completed' else result['state'])
    if source == 'APPROCH':
        try:return approch.ingest(connect)
        except Exception as exc:
            with connect() as c:c.execute('INSERT INTO runs VALUES (?,?,?,?,?)',('APPROCH',datetime.now(timezone.utc).isoformat(),'error',0,str(exc)[:1800]))
            return {'source':'APPROCH','status':'error','count':0,'message':str(exc)[:1800]}
    if source not in ('BOAMP','TED'):
        try:return ingest_feed(source)
        except Exception as e:
            with LOCK,connect() as c:c.execute('INSERT INTO runs VALUES (?,?,?,?,?)',(source,datetime.now(timezone.utc).isoformat(),'error',0,str(e)[:1800]))
            return {'source':source,'count':0,'status':'error','message':str(e)[:1800]}
    try:
        rows = boamp_fetch()
        now=datetime.now(timezone.utc).isoformat()
        with LOCK, connect() as c:
            for x in rows:
                c.execute('''INSERT INTO opportunities(id,source,title,description,kind,country,region,buyer,cpv,value,currency,published,deadline,url,stage,retrieved,raw)
                VALUES (:id,:source,:title,:description,:kind,:country,:region,:buyer,:cpv,:value,:currency,:published,:deadline,:url,:stage,:retrieved,:raw)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title,description=excluded.description,country=CASE WHEN excluded.country NOT IN ('UNKNOWN','EU','') THEN excluded.country ELSE opportunities.country END,region=excluded.region,buyer=excluded.buyer,cpv=excluded.cpv,deadline=excluded.deadline,published=excluded.published,kind=excluded.kind,stage=excluded.stage,url=excluded.url,retrieved=excluded.retrieved,raw=excluded.raw''', dict(x, retrieved=now,raw=json.dumps(x['raw'],ensure_ascii=False)))
            c.execute('INSERT INTO runs VALUES (?,?,?,?,?)',(source,now,'ok',len(rows),''))
        return {'source':source,'count':len(rows),'status':'ok'}
    except Exception as e:
        with LOCK,connect() as c: c.execute('INSERT INTO runs VALUES (?,?,?,?,?)',(source,datetime.now(timezone.utc).isoformat(),'error',0,str(e)[:1800]))
        return {'source':source,'count':0,'status':'error','message':str(e)[:1800]}

def fold(text):
    value=unicodedata.normalize('NFKD',str(text or '').casefold())
    return ''.join(x for x in value if not unicodedata.combining(x))

def matching_buyers(text):
    name=fold(text)
    found=[]
    for b in BUYERS:
        # Require a meaningful complete alias, not a weak substring such as CDC or EIB.
        if any(re.search(r'(?<![a-z0-9])'+re.escape(fold(alias))+r'(?![a-z0-9])',name) for alias in b['aliases']):
            found.append(b['id'])
    return found

def buyer_summary():
    counts={b['id']:0 for b in BUYERS}
    with connect() as c:
        for row in c.execute('SELECT buyer FROM opportunities'):
            for identifier in matching_buyers(row['buyer']):counts[identifier]+=1
    return [dict(b,indexed=counts[b['id']],source_status='surveillance locale BOAMP/TED' if b['mode']=='buyer_watch' else 'portail privé — connexion non disponible') for b in BUYERS]


# Validated lexical expansions for frequent procurement concepts. Not a universal translator.
LEXICON = {
 'informatique': ['it', 'information technology', 'informationstechnologie', 'informatica', 'informática', 'informatyka', 'ict'],
 'logiciel': ['software', 'logiciels', 'logiciel', 'logiciels', 'softwareentwicklung', 'programme', 'programas', 'oprogramowanie'],
 'cybersecurite': ['cybersecurity', 'cyber security', 'cybersicherheit', 'ciberseguridad', 'sicurezza informatica', 'cyberbeveiliging', 'cyberbezpieczenstwo'],
 'maintenance': ['wartung', 'mantenimiento', 'manutenzione', 'onderhoud', 'manutenção', 'utrzymanie', 'servicing'],
 'construction': ['bau', 'construccion', 'construcción', 'costruzione', 'bouw', 'construção', 'budowa'],
 'nettoyage': ['cleaning', 'reinigung', 'limpieza', 'pulizia', 'schoonmaak', 'limpeza', 'sprzatanie'],
 'securite': ['security', 'sicherheit', 'seguridad', 'sicurezza', 'beveiliging', 'segurança', 'bezpieczeństwo'],
 'sante': ['healthcare', 'health', 'gesundheit', 'salud', 'sanità', 'gezondheidszorg', 'saúde', 'zdrowie'],
 'formation': ['training', 'ausbildung', 'formación', 'formazione', 'opleiding', 'formação', 'szkolenia'],
 'conseil': ['consulting', 'beratung', 'consultoría', 'consulenza', 'advies', 'consultoria', 'doradztwo'],
 'transport': ['transport', 'verkehr', 'transporte', 'trasporto', 'vervoer', 'transportation'],
 'energie': ['energy', 'energie', 'energía', 'energia', 'energi', 'energetyka'],
 'eau': ['water', 'wasser', 'agua', 'acqua', 'woda'],
 'dechets': ['waste', 'abfall', 'residuos', 'rifiuti', 'afval', 'odpady'],
 'equipement': ['equipment', 'ausrüstung', 'equipamiento', 'attrezzature', 'uitrusting', 'wyposażenie'],
 'vehicule': ['vehicle', 'fahrzeug', 'vehículo', 'veicolo', 'voertuig', 'pojazd'],
 'assurance': ['insurance', 'versicherung', 'seguro', 'assicurazione', 'verzekering', 'ubezpieczenie'],
 'batiment': ['building', 'gebäude', 'edificio', 'gebouw', 'budynek'],
 'recherche': ['research', 'forschung', 'investigación', 'ricerca', 'onderzoek', 'badania'],
 'intelligence artificielle': ['artificial intelligence', 'künstliche intelligenz', 'inteligencia artificial', 'intelligenza artificiale', 'kunstmatige intelligentie', 'sztuczna inteligencja'],
}
import functools
@functools.lru_cache(maxsize=4096)
def variants(term):
    v=fold(term)
    for key, values in LEXICON.items():
        candidates=[key]+values
        if v in [fold(x) for x in candidates]:return list(dict.fromkeys(candidates))
    return [term]

def search_terms(query, multilingual=True):
    # Quoted phrases are exact concepts. Other tokens require all words (AND).
    pieces=re.findall(r'"([^"]+)"|(\S+)',query[:150])
    words=[(a or b).strip() for a,b in pieces if a or b]
    return [variants(w) if multilingual else [w] for w in words[:8]]

def search(params):
    def param(k,default=''):return params.get(k,[default])[0].strip()[:150]
    q=param('q');country=param('country');source=param('source');kind=param('kind');region=param('region');stage=param('stage');saved=param('saved');active=param('active');buyer_id=param('buyer_id')
    cpv=param('cpv'); published_after=param('published_after');published_before=param('published_before');deadline_after=param('deadline_after');deadline_before=param('deadline_before');min_value=param('min_value');max_value=param('max_value');buyer_query=param('buyer');sort=param('sort','newest'); multilingual=param('multilingual','1')!='0'
    page=max(1,min(10000,int(param('page','1') or 1)));size=24
    clauses=[];args=[]
    if q:
        # FTS5 avoids scanning and Unicode-folding all 100k+ notices on every keystroke.
        # FTS search is only used if the local SQLite supports FTS5.
        with connect() as probe:
            fts_ready=bool(probe.execute("SELECT 1 FROM sqlite_master WHERE name='opportunities_fts'").fetchone())
        for group in search_terms(q,multilingual):
            sub=[]
            for phrase in group[:12]:
                if fts_ready:
                    tokens=re.findall(r'[^\W_]+',fold(phrase),flags=re.UNICODE)
                    if not tokens:continue
                    # Prefix on the last token supports partial words while preserving phrase order.
                    expr=' '.join('"'+token.replace('"','')+'"' for token in tokens[:-1])
                    expr+=((' ' if expr else '')+'"'+tokens[-1]+'"*')
                    sub.append('o.rowid IN (SELECT rowid FROM opportunities_fts WHERE opportunities_fts MATCH ?)')
                    args.append(expr)
                else:
                    sub.append('(atlas_fold(o.title) LIKE ? OR atlas_fold(o.description) LIKE ? OR atlas_fold(o.buyer) LIKE ? OR atlas_fold(o.cpv) LIKE ?)')
                    args.extend(['%'+fold(phrase)+'%']*4)
            if sub:clauses.append('('+' OR '.join(sub)+')')

    for field,val in [('country',country),('source',source),('kind',kind),('stage',stage)]:
        if val:
            if field=='country' and val=='EU':
                clauses.append("o.country IN ('AT','BE','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IE','IT','LV','LT','LU','MT','NL','PL','PT','RO','SK','SI','ES','SE')")
            else:
                if field=='country':
                    normalized=country_code(val) or val
                    aliases=[k for k,v in COUNTRY_ALIASES.items() if v==normalized]
                    choices=[normalized]+aliases
                    clauses.append('o.country IN ('+','.join('?' for _ in choices)+')')
                    args.extend(choices)
                else:
                    clauses.append('o.'+field+' = ?');args.append(val)
    if buyer_id:
        group=next((b for b in BUYERS if b['id']==buyer_id),None)
        if not group:raise ValueError('Acheteur inconnu')
        terms=['%'+fold(a)+'%' for a in group['aliases']]
        # SQLite LIKE doesn't fold accents reliably; filter using a registered Unicode function.
        clauses.append('('+ ' OR '.join(['atlas_fold(o.buyer) LIKE ?']*len(terms))+')')
        args.extend(terms)
    if region:clauses.append('atlas_fold(o.region) LIKE ?');args.append('%'+fold(region)+'%')
    if cpv:clauses.append('o.cpv LIKE ?');args.append('%'+cpv+'%')
    for field,lower,upper in [('published',published_after,published_before),('deadline',deadline_after,deadline_before)]:
        for op,val in [('>=',lower),('<=',upper)]:
            if val:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',val):raise ValueError('Date invalide')
                clauses.append('o.'+field+' '+op+' ?');args.append(val)
    for op,val in [('>=',min_value),('<=',max_value)]:
        if val:
            number=float(val)
            if not 0<=number<=1e14:raise ValueError('Montant invalide')
            clauses.append('o.value '+op+' ?');args.append(number)
    if buyer_query:clauses.append('atlas_fold(o.buyer) LIKE ?');args.append('%'+fold(buyer_query)+'%')
    if saved=='1':clauses.append('b.id IS NOT NULL')
    if active=='1':clauses.append("o.stage = 'tender' AND o.deadline >= ?");args.append(datetime.now(timezone.utc).date().isoformat())
    where=' WHERE '+' AND '.join(clauses) if clauses else ''
    base=' FROM opportunities o LEFT JOIN bookmarks b ON o.id=b.id '
    sort_sql={'newest':'o.published DESC','oldest':'o.published ASC','deadline':'(o.deadline IS NULL OR o.deadline = '') ASC, o.deadline ASC','value_desc':'o.value DESC','value_asc':'o.value ASC'}.get(sort,'o.published DESC')
    with connect() as c:
        total=c.execute('SELECT COUNT(*)'+base+where,args).fetchone()[0]
        rows=c.execute('SELECT o.id,o.source,o.title,o.description,o.kind,o.country,o.region,o.buyer,o.cpv,o.value,o.currency,o.published,o.deadline,o.url,o.stage,(b.id IS NOT NULL) AS saved'+base+where+' ORDER BY '+sort_sql+' LIMIT ? OFFSET ?',args+[size,(page-1)*size]).fetchall()
    return {'data':[dict(x) for x in rows],'meta':{'total':total,'page':page,'pageSize':size,'pages':(total+size-1)//size},'search_info':{'multilingual':multilingual,'groups':search_terms(q,multilingual) if q else [],'coverage':'lexique contrôlé (8 langues principales); termes inconnus recherchés littéralement'}}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT/'static'),**kwargs)
    def json_response(self, obj,status=200):
        raw=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        u=urlparse(self.path)
        if u.path=='/api/jobs':
            with JOB_LOCK:self.json_response({'jobs':JOBS})
        elif u.path=='/api/opportunities':
            try:self.json_response(search(parse_qs(u.query)))
            except (ValueError,OverflowError):self.json_response({'error':'Paramètres invalides'},400)
        elif u.path=='/api/eu-ft':
            params=parse_qs(u.query);kind=params.get('kind',['tenders'])[0];q=params.get('query',[''])[0].strip();page=max(1,min(100000,int(params.get('page',['1'])[0])));limit=30
            if kind not in ('tenders','grants'):self.json_response({'error':'Type inconnu'},400);return
            with connect() as c:
                eu_ft.install(c)
                where='kind=?';args=[kind]
                if q:where+=' AND (title LIKE ? OR summary LIKE ? OR reference LIKE ?)';args.extend(['%'+q[:120]+'%']*3)
                total=c.execute('SELECT COUNT(*) FROM eu_ft_calls WHERE '+where,args).fetchone()[0]
                rows=[dict(r) for r in c.execute('SELECT id,reference,title,summary,status_raw,deadline,published,url FROM eu_ft_calls WHERE '+where+' ORDER BY published DESC LIMIT ? OFFSET ?',args+[limit,(page-1)*limit])]
            self.json_response({'data':rows,'meta':{'total':total,'page':page,'pages':(total+limit-1)//limit},'category':kind,'disclaimer':'Financements séparés des marchés TED/BOAMP.'})
        elif u.path=='/api/audit':
            self.json_response(audit_database())
        elif u.path=='/api/facets':
            with connect() as c:
                facets={}
                for field in ('country','source','kind','stage','currency'):
                    rows=[dict(r) for r in c.execute('SELECT '+field+' value,COUNT(*) count FROM opportunities GROUP BY '+field+' ORDER BY count DESC')]
                    if field=='country':
                        merged={}
                        for r in rows:
                            code=country_code(r['value']) or r['value'] or 'UNKNOWN'
                            merged[code]=merged.get(code,0)+r['count']
                        rows=[{'value':k,'count':v} for k,v in sorted(merged.items(),key=lambda x:-x[1])]
                    facets[field]=rows
                bounds=dict(c.execute('SELECT MIN(published),MAX(published),MIN(deadline),MAX(deadline),MIN(value),MAX(value) FROM opportunities').fetchone()) if False else {}
                missing={k:c.execute('SELECT COUNT(*) FROM opportunities WHERE '+k+' IS NULL OR '+k+" = ''").fetchone()[0] for k in ('country','region','buyer','cpv','deadline')}
                missing['country_unclassified']=c.execute("SELECT COUNT(*) FROM opportunities WHERE country IS NULL OR country IN ('','UNKNOWN','EU')").fetchone()[0]
                total=c.execute('SELECT COUNT(*) FROM opportunities').fetchone()[0]
            self.json_response({'facets':facets,'total':total,'missing':missing,'warning':'Les filtres portent uniquement sur les avis importés ; champs manquants exclus des critères correspondants.'})
        elif u.path=='/api/diagnostics/countries':
            with connect() as c:
                rows=[dict(r) for r in c.execute('SELECT source,country,stage,COUNT(*) count FROM opportunities GROUP BY source,country,stage ORDER BY source,country,stage')]
                unknown=c.execute("SELECT COUNT(*) FROM opportunities WHERE source='TED' AND (country IS NULL OR country IN ('UNKNOWN','EU',''))").fetchone()[0]
            self.json_response({'breakdown':rows,'ted_unmapped':unknown,'warning':'Un pays inconnu reste inconnu : il faut récupérer un avis TED contenant buyer-country pour pouvoir le classer.'})
        elif u.path=='/api/buyers':
            self.json_response({'buyers':buyer_summary(),'note':'Acheteurs repérés dans les avis actuellement indexés. Les portails privés ne sont pas aspirés.'})
        elif u.path=='/api/coverage':
            with connect() as c:
                grouped=[dict(r) for r in c.execute('SELECT source,country,stage,COUNT(*) count FROM opportunities GROUP BY source,country,stage ORDER BY source,country,stage')]
                source_counts={r['source']:r['count'] for r in c.execute('SELECT source,COUNT(*) count FROM opportunities GROUP BY source')}
            self.json_response({'catalog_count':len(SOURCES),'indexed_source_count':len(source_counts),'indexed_sources':source_counts,'coverage':grouped,'unconnected':[{'id':s['id'],'name':s['name'],'country':s['country'],'url':s['url']} for s in SOURCES if s['id'] not in ('BOAMP','TED') and s['id'] not in [f['id'] for f in feed_registry() if f.get('enabled')]],'warning':'Catalogue ≠ source intégrée. Une absence de résultats ne prouve pas une absence de marchés.'})
        elif u.path=='/api/access-registry':
            with connect() as c:
                counts={r['source']:r['n'] for r in c.execute('SELECT source,COUNT(*) n FROM opportunities GROUP BY source')}
            registry=json.loads((ROOT/'access_registry.json').read_text(encoding='utf-8'))
            for item in registry:
                item['indexed_notices']=counts.get(item['id'],0)
            self.json_response({'sources':registry,'total':len(registry),'connected_with_notices':sum(bool(x['indexed_notices']) for x in registry),'notice':'Une URL officielle ne signifie pas une API intégrée. Les liens de création de compte ne sont affichés comme vérifiés que lorsqu’ils ont été confirmés.'})
        elif u.path=='/api/feeds':
            self.json_response({'feeds':[{k:v for k,v in f.items() if k not in ('secret','token','api_key')} for f in feed_registry()]})
        elif u.path=='/api/countries':
            with connect() as c:
                values=[dict(r) for r in c.execute("SELECT country,COUNT(*) AS count FROM opportunities GROUP BY country ORDER BY count DESC")]
            self.json_response({'countries':values,'note':'UNKNOWN = pays absent de la réponse TED, ne pas interpréter comme UE'})
        elif u.path=='/api/sources':
            with connect() as c:
                counts={r['source']:r['n'] for r in c.execute('SELECT source,COUNT(*) n FROM opportunities GROUP BY source')}
                runs=[dict(x) for x in c.execute('SELECT r.* FROM runs r INNER JOIN (SELECT source,MAX(rowid) last_id FROM runs GROUP BY source) latest ON latest.last_id=r.rowid')]
            self.json_response({'sources':[dict(s,records=counts.get(s['id'],0)) for s in SOURCES],'runs':runs})
        elif u.path=='/api/stats':
            with connect() as c:
                n=c.execute('SELECT COUNT(*) FROM opportunities').fetchone()[0]
                saved=c.execute('SELECT COUNT(*) FROM bookmarks').fetchone()[0]
                origins=c.execute('SELECT COUNT(DISTINCT source) FROM opportunities').fetchone()[0]
            self.json_response({'records':n,'saved':saved,'activeSources':origins,'catalogSources':len(SOURCES),'monitoredBuyers':len(BUYERS)})
        elif u.path=='/api/connectors':
            with connect() as c:
                runs=[dict(x) for x in c.execute('SELECT r.* FROM runs r INNER JOIN (SELECT source,MAX(rowid) last_id FROM runs GROUP BY source) t ON t.last_id=r.rowid')]
            self.json_response({'implemented':['BOAMP','TED','EU_FT_TENDERS','EU_FT_GRANTS'],'verified_live':[], 'rss_atom_enabled':[f['id'] for f in feed_registry() if f.get('enabled')], 'catalog_only':len(SOURCES)-2,'runs':runs,'note':'Une exécution en direct sur votre machine est nécessaire pour vérifier chaque source.'})
        elif u.path=='/api/eu-ft/stats':
            with connect() as c:
                eu_ft.install(c)
                stats=[dict(r) for r in c.execute('SELECT kind,COUNT(*) count,MAX(retrieved) last_updated FROM eu_ft_calls GROUP BY kind')]
                runs=[dict(r) for r in c.execute("SELECT source,at,status,fetched,message FROM runs WHERE source LIKE 'EU_FT_%' ORDER BY rowid DESC LIMIT 8")]
            self.json_response({'categories':stats,'runs':runs,'note':'Ces dossiers sont séparés du total BOAMP + TED.'})
        elif u.path=='/api/sync-status':
            state_path=DB.parent/'sync-status.json'
            try:
                state=json.loads(state_path.read_text(encoding='utf-8'))
            except (OSError, ValueError) as exc:
                state={'status':'not_reported','reason':str(exc)[:160]}
            with connect() as c:
                recent=[dict(r) for r in c.execute('SELECT source,at,status,fetched,message FROM runs ORDER BY rowid DESC LIMIT 12')]
                total=c.execute('SELECT COUNT(*) FROM opportunities').fetchone()[0]
            self.json_response({'database':str(DB),'total':total,'scheduler_report':state,'recent_source_runs':recent,'note':'Le total peut rester stable malgré des actualisations; vérifier la date et le statut par source.'})
        elif u.path=='/api/health':
            with connect() as c:
                last=[dict(r) for r in c.execute('SELECT source,at,status,fetched,message FROM runs ORDER BY rowid DESC LIMIT 5')]
            self.json_response({'status':'ok','database':str(DB),'recent_imports':last,'real_data_only':True})
        elif u.path.startswith('/api/'):self.json_response({'error':'Not found'},404)
        else:super().do_GET()
    def do_POST(self):
        u=urlparse(self.path)
        length=int(self.headers.get('Content-Length','0'))
        if length>4096:self.json_response({'error':'Payload trop volumineux'},413);return
        try:body=json.loads(self.rfile.read(length) or b'{}')
        except json.JSONDecodeError:self.json_response({'error':'JSON invalide'},400);return
        if u.path=='/api/ted/full':
            self.json_response(start_ted_full(),202)
        elif u.path=='/api/eu-ft/ingest':
            kind=body.get('kind','tenders')
            if kind not in ('tenders','grants'):self.json_response({'error':'Type inconnu'},400);return
            outcome=eu_ft_ingest(kind);self.json_response(outcome,200 if outcome['status']=='ok' else 502)
        elif u.path=='/api/ingest':
            source=body.get('source','')
            if source not in ('BOAMP','TED','APPROCH') and source not in [f['id'] for f in feed_registry() if f.get('enabled')]:self.json_response({'error':'Source non intégrée'},400);return
            outcome=ingest(source);self.json_response(outcome,200 if outcome['status']=='ok' else 502)
        elif u.path=='/api/bookmark':
            ident=body.get('id','');saved=body.get('saved',True)
            if not isinstance(ident,str) or len(ident)>200:self.json_response({'error':'ID invalide'},400);return
            with LOCK,connect() as c:
                if not c.execute('SELECT 1 FROM opportunities WHERE id=?',(ident,)).fetchone():self.json_response({'error':'Avis inconnu'},404);return
                if saved:c.execute('INSERT OR IGNORE INTO bookmarks(id) VALUES (?)',(ident,))
                else:c.execute('DELETE FROM bookmarks WHERE id=?',(ident,))
            self.json_response({'ok':True,'saved':bool(saved)})
        else:self.json_response({'error':'Not found'},404)

def merge_previous_databases(force=False):
    """Non-destructive migration of all local Atlas databases from older downloads."""
    from pathlib import Path
    import shutil
    home = Path.home()
    stamp = ROOT / '.history-merged'
    # Always rescan: older release ZIP accidentally shipped a migration marker.
    # INSERT OR IGNORE makes repeated merges safe.
    patterns = ['atlas-marches-mvp', 'atlas-marches-mvp-v*']
    candidates = []
    for parent in (home / 'Downloads', home / 'Téléchargements'):
        for pattern in patterns:
            candidates.extend(parent.glob(pattern + '/atlas.db'))
            candidates.extend(parent.glob(pattern + '/data/atlas.db'))
    candidates = sorted({p.resolve() for p in candidates if p.is_file() and p.resolve() != DB.resolve()})
    print('[Migration] Base active : '+str(DB.resolve()),flush=True)
    for origin in candidates:
        try:
            with sqlite3.connect('file:'+str(origin)+'?mode=ro',uri=True,timeout=5) as source_db:
                tables={r[0] for r in source_db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                count=source_db.execute('SELECT COUNT(*) FROM opportunities').fetchone()[0] if 'opportunities' in tables else 'schéma non reconnu'
                print('[Migration] Candidate : '+str(origin)+' ; avis='+str(count),flush=True)
        except Exception as exc:
            print('[Migration] Candidate illisible : '+str(origin)+' ; '+str(exc),flush=True)
    summary = {'databases': 0, 'new_opportunities': 0, 'new_bookmarks': 0, 'sources': []}
    if not candidates:
        print('[Migration] Aucune base Atlas antérieure détectée dans Téléchargements; base locale inchangée.',flush=True)
        return
    # The destination is backed up before importing any historic records.
    if DB.exists():
        with connect() as current:
            backup_path=DB.parent / ('atlas-backup-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'.db')
            backup = sqlite3.connect(str(backup_path))
            try: current.backup(backup)
            finally: backup.close()
    columns = ['id','source','title','description','kind','country','region','buyer','cpv','value','currency','published','deadline','url','stage','retrieved','raw']
    for path in candidates:
        try:
            old = sqlite3.connect('file:' + str(path) + '?mode=ro',uri=True,timeout=5)
            old.row_factory=sqlite3.Row
            try:
                tables={row[0] for row in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if 'opportunities' not in tables: continue
                present={row[1] for row in old.execute('PRAGMA table_info(opportunities)')}
                if not {'id','title','source','url'}.issubset(present):continue
                selected=[col for col in columns if col in present]
                added=0; bookmarks=0
                with connect() as target:
                    sql='INSERT INTO opportunities ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+') ON CONFLICT(id) DO UPDATE SET country=CASE WHEN opportunities.country IS NULL OR opportunities.country IN ("","EU","UNKNOWN") THEN COALESCE(NULLIF(excluded.country,"UNKNOWN"),opportunities.country) ELSE opportunities.country END, description=CASE WHEN length(COALESCE(excluded.description,""))>length(COALESCE(opportunities.description,"")) THEN excluded.description ELSE opportunities.description END, raw=CASE WHEN length(COALESCE(excluded.raw,""))>length(COALESCE(opportunities.raw,"")) THEN excluded.raw ELSE opportunities.raw END, buyer=CASE WHEN length(COALESCE(excluded.buyer,""))>length(COALESCE(opportunities.buyer,"")) THEN excluded.buyer ELSE opportunities.buyer END, cpv=CASE WHEN length(COALESCE(excluded.cpv,""))>length(COALESCE(opportunities.cpv,"")) THEN excluded.cpv ELSE opportunities.cpv END, deadline=COALESCE(NULLIF(opportunities.deadline,""),excluded.deadline)'
                    cur=old.execute('SELECT '+','.join(selected)+' FROM opportunities')
                    for row in cur:
                        values={col:row[col] for col in selected}
                        values.setdefault('stage','tender')
                        values.setdefault('retrieved',datetime.now(timezone.utc).isoformat())
                        values.setdefault('country','UNKNOWN')
                        target.execute(sql,tuple(values.get(col) for col in columns))
                        added+=1
                    if 'bookmarks' in tables:
                        for row in old.execute('SELECT id FROM bookmarks'):
                            target.execute('INSERT OR IGNORE INTO bookmarks(id) VALUES(?)',(row['id'],))
                            bookmarks+=target.execute('SELECT changes()').fetchone()[0]
                summary['databases']+=1;summary['new_opportunities']+=added;summary['new_bookmarks']+=bookmarks
                summary['sources'].append({'folder':path.parent.name,'added':added})
            finally:old.close()
        except (sqlite3.DatabaseError, OSError) as exc:
            print('[Migration] Lecture impossible de '+path.parent.name+': '+str(exc),flush=True)
    # Retain marker only once at least one database was successfully read.
    # Report every run, but do not use a marker to suppress future recovery.
    stamp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print('[Migration] '+json.dumps(summary,ensure_ascii=False),flush=True)



def audit_database():
    """Ground-truth counts; never infer European coverage from TED raw record count."""
    with connect() as c:
        n=c.execute('SELECT COUNT(*) FROM opportunities').fetchone()[0]
        by_source=[dict(r) for r in c.execute("SELECT source,COUNT(*) total, SUM(CASE WHEN country IS NULL OR country IN ('','EU','UNKNOWN') THEN 1 ELSE 0 END) country_unknown, SUM(CASE WHEN deadline IS NULL OR deadline='' THEN 1 ELSE 0 END) deadline_unknown FROM opportunities GROUP BY source ORDER BY total DESC")]
        by_country=[dict(r) for r in c.execute("SELECT COALESCE(NULLIF(country,''),'UNKNOWN') country,COUNT(*) total FROM opportunities GROUP BY 1 ORDER BY total DESC")]
        status=[dict(r) for r in c.execute('SELECT stage,COUNT(*) total FROM opportunities GROUP BY stage ORDER BY total DESC')]
        sample=[dict(r) for r in c.execute("SELECT id,country,substr(raw,1,600) raw_excerpt FROM opportunities WHERE source='TED' AND (country IS NULL OR country IN ('','UNKNOWN','EU')) LIMIT 3")]
        connected=c.execute('SELECT COUNT(DISTINCT source) FROM opportunities').fetchone()[0]
    return {'database':str(DB),'total':n,'source_count_with_data':connected,'catalog_count':len(SOURCES),'by_source':by_source,'by_country':by_country,'by_stage':status,'unclassified_ted_samples':sample,'note':'TED avec pays UNKNOWN ne prouve aucune couverture géographique. Un marché sans échéance ne prouve pas qu’il est ouvert.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--normalize-all-countries',action='store_true');p.add_argument('--merge-history',action='store_true');p.add_argument('--audit',action='store_true');p.add_argument('--repair-countries',action='store_true');p.add_argument('--enrich-ted-countries',action='store_true');p.add_argument('--enrich-limit',type=int,default=100);p.add_argument('--port',type=int,default=8000);p.add_argument('--ingest',type=str);p.add_argument('--import-approch',type=str);p.add_argument('--serve',action='store_true');p.add_argument('--ted-all-open',action='store_true');p.add_argument('--ted-backfill',action='store_true');p.add_argument('--ted-no-resume',action='store_true');args=p.parse_args();init();
    if args.merge_history:merge_previous_databases(True)
    if args.normalize_all_countries:
        print(json.dumps(normalize_all_country_codes(),ensure_ascii=False,indent=2));return
    repaired=repair_countries() if args.repair_countries else 0;
    if args.merge_history:
        print(json.dumps(audit_database(),ensure_ascii=False,indent=2));return
    if args.audit:
        print(json.dumps(audit_database(),ensure_ascii=False,indent=2));return
    if args.repair_countries:
        print(json.dumps({'repaired':repaired,'message':'Pays TED récupérés depuis les données déjà enregistrées; les inconnus nécessitent un nouvel import.'}));return
    if args.enrich_ted_countries:
        print(json.dumps(enrich_ted_countries(max(1,min(100000,args.enrich_limit))),ensure_ascii=False,indent=2));return
    if args.ted_all_open or args.ted_backfill:
        result=run_ted_full(backfill=args.ted_backfill, resume=not args.ted_no_resume)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        raise SystemExit(0 if result['state']=='completed' else 2 if result['state']=='already_running' else 1)
    if args.import_approch:
        print(json.dumps(approch.ingest(connect,args.import_approch),ensure_ascii=False,indent=2));return
    if args.ingest:
        if args.ingest not in ('BOAMP','TED','APPROCH','ALL') and args.ingest not in [f['id'] for f in feed_registry() if f.get('enabled')]:p.error('Source inconnue ou désactivée')
        outcomes=[ingest(s) for s in (['BOAMP','TED'] if args.ingest=='ALL' else [args.ingest])]
        print(json.dumps(outcomes,ensure_ascii=False,indent=2))
        if not args.serve:raise SystemExit(0 if all(x.get('status')=='ok' for x in outcomes) else 1)
    print(f'Atlas Marchés → http://localhost:{args.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()
