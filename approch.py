"""APProch advance procurement projects. Public bulk export + user CSV/XLSX import; no external dependencies."""
import csv, io, json, re, zipfile, hashlib, urllib.request, unicodedata
from pathlib import Path
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

EXPORT_URL='https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/projets-dachats-publics/exports/csv?lang=fr&timezone=Europe%2FParis&use_labels=true&delimiter=%3B'
SOURCE='APPROCH'

def norm(s):
    return ''.join(ch for ch in unicodedata.normalize('NFKD',str(s or '').casefold()) if not unicodedata.combining(ch))

def xlsx_rows(path):
    ns={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            root=ET.fromstring(z.read('xl/sharedStrings.xml'))
            strings=[''.join(t.text or '' for t in si.findall('.//x:t',ns)) for si in root.findall('x:si',ns)]
        sheets=sorted(n for n in z.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',n))
        if not sheets: raise ValueError('Aucune feuille dans le fichier XLSX')
        root=ET.fromstring(z.read(sheets[0])); out=[]
        for r in root.findall('.//x:sheetData/x:row',ns):
            row={}
            for cell in r.findall('x:c',ns):
                ref=cell.get('r',''); m=re.match('[A-Z]+',ref)
                if not m: continue
                idx=0
                for ch in m.group():idx=idx*26+ord(ch)-64
                v=cell.find('x:v',ns)
                if cell.get('t')=='inlineStr': value=''.join(x.text or '' for x in cell.findall('.//x:t',ns))
                elif v is None: value=''
                elif cell.get('t')=='s': value=strings[int(v.text)]
                else: value=v.text or ''
                row[idx-1]=value
            if row: out.append([row.get(i,'') for i in range(max(row)+1)])
        return out

def table_rows(data,ext):
    if ext=='.xlsx':
        rows=xlsx_rows(data)
        header=next((i for i,r in enumerate(rows) if any(norm(v)=='libelle' for v in r) and any('acheteuse' in norm(v) for v in r)),None)
        if header is None:raise ValueError('En-tête APProch non trouvé dans XLSX')
        return [dict(zip(rows[header],r)) for r in rows[header+1:] if any(str(v).strip() for v in r)]
    text=data.decode('utf-8-sig') if isinstance(data,bytes) else Path(data).read_text(encoding='utf-8-sig')
    dialect=csv.Sniffer().sniff(text[:15000],delimiters=';,\t')
    return list(csv.DictReader(io.StringIO(text),dialect=dialect))

def field(row,*keys):
    # Harmonize Opendatasoft export labels and technical field identifiers.
    def canonical(value):
        return ' '.join(re.findall(r'[a-z0-9]+', norm(value.replace('\\ufeff','').replace('_',' '))))
    vals={canonical(k):v for k,v in row.items() if isinstance(k,str) and k}
    for key in keys:
        v=vals.get(canonical(key))
        if v is not None and str(v).strip() not in ('','27','None','null'):
            return str(v).strip()
    return ''

def iso_date(s):
    if not s:return None
    s=str(s).strip()
    for fmt in ('%d/%m/%Y','%Y-%m-%d','%Y-%m-%dT%H:%M:%S'):
        try:return datetime.strptime(s[:19] if 'T' in s else s,fmt).date().isoformat()
        except ValueError:pass
    return None

def convert(row):
    title=field(row,'Libellé','libelle','titre','title','objet', 'libellé du projet', 'nom du projet')
    buyer=field(row,'Entité acheteuse','entite_acheteuse','acheteur',
                "Nom de l'entité acheteuse", 'Nom de l entité acheteuse',
                'denomination_entite_acheteuse', 'nom_entite_acheteuse',
                'organisation', 'nom_acheteur')
    link=field(row,'Lien vers la consultation','lien_vers_la_consultation','url')
    if not title or not buyer:return None
    raw_id=field(row,'id','identifiant','id_projet','recordid','reference')
    fingerprint=raw_id or hashlib.sha256((norm(title)+'|'+norm(buyer)+'|'+link).encode()).hexdigest()[:24]
    # Different projects may share a reference in different source systems; keep namespace.
    key='APPROCH-'+hashlib.sha256(str(fingerprint).encode()).hexdigest()[:28]
    cpv=field(row,'Code(s) CPV','codes_cpv','cpv')
    category=field(row,"Catégorie d'achat",'categorie_achat','nature')
    return {'id':key,'source':SOURCE,'title':title,'description':field(row,'Description','description'),
            'kind':'FUTURE_PROJECT','country':'FR','region':field(row,"Département(s) d'exécution du marché",'departement'),
            'buyer':buyer,'cpv':cpv,'value':None,'currency':'EUR',
            'published':iso_date(field(row,'Première mise en ligne','premiere_mise_en_ligne','date_publication')),
            'deadline':None, # Forecast dates are not confirmed bid deadlines
            'url':link or 'https://projets-achats.marches-publics.gouv.fr/',
            'stage':'future',
            'raw':json.dumps({'original':row,'category':category,'forecast_publication':field(row,'Date cible de publication'),
                  'forecast_submission':field(row,'Date cible de remise des offres'),
                  'portal_status':field(row,'Statut'),'exchange_status':field(row,"État de l'espace d'échanges")},ensure_ascii=False)}

def ingest(connect,source_file=None):
    if source_file:
        p=Path(source_file)
        if p.suffix.lower() not in ('.xlsx','.csv'):raise ValueError('Formats acceptés : CSV, XLSX')
        rows=table_rows(p,p.suffix.lower())
    else:
        req=urllib.request.Request(EXPORT_URL,headers={'User-Agent':'AtlasMarches/1.0','Accept':'text/csv'})
        with urllib.request.urlopen(req,timeout=70) as resp:
            payload=resp.read(30*1024*1024+1)
        if len(payload)>30*1024*1024:raise ValueError('Export APProch trop volumineux')
        rows=table_rows(payload,'.csv')
    now=datetime.now(timezone.utc).isoformat()
    valid=[o for row in rows if (o:=convert(row))]
    if not valid:
        headers=sorted({str(k).replace('\ufeff','')[:80] for row in rows[:3] for k in row if k})
        raise ValueError('Aucun projet APProch valide; rows=' + str(len(rows)) +
                         '; colonnes=' + repr(headers[:40]) + '; aucune écriture')
    new=0
    with connect() as c:
        for o in valid:
            if not c.execute('SELECT 1 FROM opportunities WHERE id=?',(o['id'],)).fetchone():new+=1
            c.execute('''INSERT INTO opportunities(id,source,title,description,kind,country,region,buyer,cpv,value,currency,published,deadline,url,stage,retrieved,raw)
              VALUES (:id,:source,:title,:description,:kind,:country,:region,:buyer,:cpv,:value,:currency,:published,:deadline,:url,:stage,:retrieved,:raw)
              ON CONFLICT(id) DO UPDATE SET title=excluded.title,description=excluded.description,kind=excluded.kind,region=excluded.region,buyer=excluded.buyer,cpv=excluded.cpv,published=excluded.published,url=excluded.url,stage=excluded.stage,retrieved=excluded.retrieved,raw=excluded.raw''',dict(o,retrieved=now))
        c.execute('INSERT INTO runs VALUES (?,?,?,?,?)',(SOURCE,now,'ok',len(valid),f'new={new}; mode={"file" if source_file else "official_csv"}'))
    return {'source':SOURCE,'status':'ok','count':len(valid),'new':new,'category':'future_projects'}
