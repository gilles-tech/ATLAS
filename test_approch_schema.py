"""Regression fixtures for APProch labelled and technical Opendatasoft exports."""
import unittest
import approch

class APProchSchemaTests(unittest.TestCase):
    def test_technical_names_forecast_not_tender(self):
        item=approch.convert({'libelle':'Réhabilitation école','nom_entite_acheteuse':'Ville Exemple',
                              'date_previsionnelle_de_publication':'2027-03-15',
                              'code_s_cpv':'45200000'})
        self.assertIsNotNone(item)
        self.assertEqual(item['stage'],'future')
        self.assertEqual(item['kind'],'FUTURE_PROJECT')
        self.assertIsNone(item['deadline'])
        self.assertEqual(item['buyer'],'Ville Exemple')
    def test_live_api_shape_has_stable_code_and_siren(self):
        item=approch.convert({'code':12345, 'libelle':'Achat prévu',
            'siren_de_l_entite_acheteuse': 123456789,
            'date_previsionnelle_de_publication':'2027-03-15'})
        self.assertEqual(item['buyer'],'SIREN 123456789')
        self.assertEqual(item['kind'],'FUTURE_PROJECT')
        self.assertIsNone(item['deadline'])
        self.assertEqual(item['published'],'2027-03-15')
        again=approch.convert({'code':12345, 'libelle':'Titre modifié',
            'siren_de_l_entite_acheteuse':123456789})
        self.assertEqual(item['id'],again['id'])

    def test_labelled_names(self):
        item=approch.convert({'Libellé':'Projet de services','Nom de l’entité acheteuse':'Ministère Exemple'})
        self.assertIsNotNone(item)
        self.assertEqual(item['title'],'Projet de services')
    def test_incomplete_never_becomes_fake_opportunity(self):
        self.assertIsNone(approch.convert({'Code':'45','Date cible de publication':'2027-10-01'}))

if __name__=='__main__':
    unittest.main()
