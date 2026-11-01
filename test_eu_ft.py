import tempfile, sqlite3, unittest
from pathlib import Path
from eu_ft import query_for, multipart, collect, normalize, install

class EUFTTests(unittest.TestCase):
    def test_query_categories(self):
        self.assertEqual(query_for('tenders')['bool']['must'][0]['terms']['type'], ['0'])
        self.assertEqual(query_for('grants')['bool']['must'][0]['terms']['type'], ['1','2','8'])
    def test_multipart(self):
        body, mime=multipart({'query': ('{}','application/json')})
        self.assertIn(b'Content-Type: application/json',body)
        self.assertIn(b'name="query"',body)
        self.assertIn('boundary=',mime)
    def test_normalize_reject_missing(self):
        self.assertIsNone(normalize({'title':'No identifier'}, 'tenders'))
    def test_upsert_and_separate_storage(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'atlas.db'
            def connect(): return sqlite3.connect(path)
            def page(kind,status,page):
                return ([{'identifier':'TEST-2026-01','title':'Research contract','status':'31094501'}],{})
            one=collect(connect,'tenders',max_pages=2,fetcher=page)
            two=collect(connect,'tenders',max_pages=2,fetcher=page)
            self.assertEqual(one['new'],1)
            self.assertEqual(two['new'],0)
            with connect() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM eu_ft_calls').fetchone()[0],1)
    def test_unknown_schema_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            def connect():return sqlite3.connect(str(Path(td)/'a.db'))
            with self.assertRaisesRegex(ValueError,'aucun identifiant'):
                collect(connect,fetcher=lambda *a:([{'foo':'bar'}],{}),max_pages=1)
if __name__=='__main__':unittest.main()
