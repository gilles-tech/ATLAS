import os,tempfile,unittest,json
os.environ['ATLAS_DB']=tempfile.mktemp(suffix='.db')
import app
class AtlasTests(unittest.TestCase):
 def setUp(self):app.init()
 def test_catalog(self):
  self.assertGreaterEqual(len(app.SOURCES),80)
  for key in ['FR_DEFENSE','FR_CNRS_PUMA','FR_UNIHA','FR_CDC','FR_BPIFRANCE','EU_NATO','EU_EBRD','IT_PVL']:
   self.assertIn(key,{r['id'] for r in app.SOURCES})
 def test_countries(self):
  for raw,want in [('FRA','FR'),('DEU','DE'),('ESP','ES'),('BEL','BE'),('ITA','IT'),('CZE','CZ')]:self.assertEqual(app.country_code(raw),want)
 def test_search_combined(self):
  app.save_batch([dict(id='TED:frtest',source='TED',title='Cybersécurité armées',description='Services de sécurité',kind='service',country='FR',region='Paris',buyer='Ministère des Armées',cpv='72000000',value=None,currency='EUR',published='2026-10-30',deadline='2026-11-30',url='https://example.org/real',stage='tender',raw={'buyer-country':'FRA'}),dict(id='TED:detest',source='TED',title='Cybersicherheit',description='Service',kind='service',country='DE',region='Berlin',buyer='Bund',cpv='72000000',value=None,currency='EUR',published='2026-10-30',deadline='2026-11-30',url='https://example.org/other',stage='tender',raw={'buyer-country':'DEU'})])
  self.assertEqual(app.search({'country':['FR'],'q':['Cybersécurité']})['meta']['total'],1)
  self.assertEqual(app.search({'country':['DE'],'q':['Cybersécurité']})['meta']['total'],1)
  self.assertEqual(app.search({'country':['DE'],'q':['Cybersécurité'],'multilingual':['0']})['meta']['total'],0)
 def test_feed_disabled(self):
  self.assertEqual(app.feed_registry(),[])
  with self.assertRaises(ValueError):app.ingest_feed('FR_EXAMPLE_ATOM')
if __name__=='__main__':unittest.main()
