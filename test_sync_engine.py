import json, sqlite3, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from sync_engine import run

class SyncTests(unittest.TestCase):
    def test_counts_and_failure_visible(self):
        with tempfile.TemporaryDirectory() as temp:
            db=Path(temp)/'atlas.db'
            with sqlite3.connect(db) as c:
                c.execute('CREATE TABLE opportunities(id TEXT PRIMARY KEY, source TEXT, retrieved TEXT)')
                c.execute("INSERT INTO opportunities VALUES('old','TED','2026-01-01')")
            def ingest(name):
                if name=='BOAMP':
                    with sqlite3.connect(db) as c:
                        c.execute("INSERT INTO opportunities VALUES('new','BOAMP','2026-10-31')")
                    return {'status':'ok','count':1}
                return {'status':'error','message':'unavailable'}
            app=SimpleNamespace(DB=db,SOURCES=[1,2,3], init=lambda:None,ingest=ingest,
                                run_ted_full=lambda:{'state':'error','error':'TED refused'},feed_registry=lambda:[])
            report=run(app,Path(temp)/'sync-status.json')
            self.assertEqual(report['before']['total'],1)
            self.assertEqual(report['after']['total'],2)
            self.assertEqual(report['new_unique_records'],1)
            self.assertEqual(report['status'],'partial_error')
            self.assertIn('aucun flux', ' '.join(report['notes']).lower())
            self.assertEqual(json.loads((Path(temp)/'sync-status.json').read_text())['after']['total'],2)

if __name__=='__main__': unittest.main()
