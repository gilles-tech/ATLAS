#!/usr/bin/env python3
"""Run bounded real APProch/EU FT imports ONLY in a disposable SQLite database."""
import argparse, json, os, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',required=True,type=Path)
    args=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='atlas-sources-stage-') as tmp:
        db=Path(tmp)/'stage.db'
        os.environ['ATLAS_DB']=str(db)
        os.environ['ATLAS_EU_FT_PAGES']='1'
        import app
        import eu_ft
        from maintenance import inspect_copy
        app.init()
        before=inspect_copy(db)
        results={}
        results['APPROCH']=app.ingest('APPROCH')
        results['EU_FT_TENDERS']=app.eu_ft_ingest('tenders')
        results['EU_FT_GRANTS']=app.eu_ft_ingest('grants')
        after=inspect_copy(db)
        with app.connect() as c:
            eu_ft.install(c)
            eu_count=dict(c.execute('SELECT kind,COUNT(*) FROM eu_ft_calls GROUP BY kind').fetchall())
            forecasts=c.execute("SELECT COUNT(*) FROM opportunities WHERE source='APPROCH' AND kind='FUTURE_PROJECT' AND stage='future' AND deadline IS NULL").fetchone()[0]
        report={'schema_version':1,'production_database_touched':False,
                'before':before,'results':results,'after':after,
                'forecasts_without_fake_deadline':forecasts,
                'eu_ft_by_kind':eu_count}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(args.report),'results':results,
                      'forecasts_without_fake_deadline':forecasts,
                      'eu_ft_by_kind':eu_count},ensure_ascii=False,indent=2))
    return 0 if all(x.get('status')=='ok' and x.get('count',0)>0 for x in results.values()) else 1

if __name__=='__main__':raise SystemExit(main())
