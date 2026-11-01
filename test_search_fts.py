import os, pathlib, tempfile, unittest
from unittest.mock import patch
import app

class SearchIndexTests(unittest.TestCase):
    def test_search_and_filters(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(app, 'DB', pathlib.Path(td)/'atlas.db'):
                app.init()
                with app.connect() as c:
                    for i, country, title in [('a','DE','Cybersecurity network'),('b','FR','Cybersecurity network'),('c','DE','Travaux de bâtiment')]:
                        c.execute('INSERT INTO opportunities (id,source,title,country,url,stage,retrieved) VALUES (?,?,?,?,?,?,?)',(i,'TED',title,country,'https://ted.europa.eu','tender','2026-11-01'))
                self.assertEqual(app.search({'q':['cybersecurity']})['meta']['total'],2)
                self.assertEqual(app.search({'q':['cybersecurity'],'country':['DE']})['meta']['total'],1)
                self.assertEqual(app.search({'q':['termeintrouvable']})['meta']['total'],0)
                with app.connect() as c:c.execute("UPDATE opportunities SET title='Cybersecurity network' WHERE id='c'")
                self.assertEqual(app.search({'q':['cybersecurity'],'country':['DE']})['meta']['total'],2)
                app.init()
                self.assertEqual(app.search({'q':['cybersecurity'],'country':['DE']})['meta']['total'],2)
if __name__=='__main__':unittest.main()
