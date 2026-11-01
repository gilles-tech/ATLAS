#!/usr/bin/env python3
"""Read-only, bounded diagnostics for official APProch and EU F&T schemas."""
import argparse
import csv
import io
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import approch
import eu_ft

def fields(rows):
    result = []
    for row in rows[:2]:
        if not isinstance(row, dict):
            result.append({'type': type(row).__name__})
            continue
        doc = row.get('_source') or row.get('source') or row
        result.append({
            'top_keys': sorted(str(x) for x in row.keys())[:80],
            'top_types': {str(k): type(v).__name__ for k,v in list(row.items())[:35]},
            'document_keys': sorted(str(x) for x in doc)[:100] if isinstance(doc,dict) else [],
            'document_types': {str(k):type(v).__name__ for k,v in list(doc.items())[:40]} if isinstance(doc,dict) else {}
        })
    return result

def approch_probe():
    # Query 3 public records rather than downloading/processing the entire CSV.
    url = ('https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/'
           'projets-dachats-publics/records?' + urlencode({'limit':3}))
    req = Request(url, headers={'User-Agent':'AtlasMarches/source-probe-1',
                                'Accept':'application/json'})
    with urlopen(req, timeout=20) as response:
        data = response.read(256_001)
    if len(data)>256_000: raise ValueError('APProch JSON response exceeds 256KB')
    body=json.loads(data)
    records=body.get('results')
    if not isinstance(records,list): raise ValueError('No APProch results list')
    return {'endpoint':'official Opendatasoft records API',
            'received':len(records),'total_count':body.get('total_count'),
            'schema':fields(records),
            'adapter_valid_count':sum(approch.convert(x) is not None for x in records)}

def eu_probe(kind):
    hits,response=eu_ft.fetch_page(kind,'open',1,page_size=2)
    return {'endpoint':'EU F&T official SEDIA search API','kind':kind,
            'received':len(hits), 'response_top_keys':sorted(str(k) for k in response)[:70],
            'schema':fields(hits),
            'adapter_valid_count':sum(eu_ft.normalize(row,kind) is not None for row in hits)}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',required=True,type=Path)
    args=p.parse_args()
    result={'schema_version':1,'database_touched':False,'sources':{}}
    for name,fn in [('APPROCH',approch_probe),
                    ('EU_FT_TENDERS',lambda:eu_probe('tenders')),
                    ('EU_FT_GRANTS',lambda:eu_probe('grants'))]:
        try:
            result['sources'][name]={'status':'ok',**fn()}
        except Exception as exc:
            # Avoid leaking response bodies and HTTP credentials to report.
            result['sources'][name]={'status':'error','error_type':type(exc).__name__,
                                     'error_summary':str(exc)[:160] if not isinstance(exc, OSError) else type(exc).__name__}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if all(x['status']=='ok' for x in result['sources'].values()) else 1

if __name__=='__main__': raise SystemExit(main())
