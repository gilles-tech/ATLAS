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
    def test_labelled_names(self):
        item=approch.convert({'Libellé':'Projet de services','Nom de l’entité acheteuse':'Ministère Exemple'})
        self.assertIsNotNone(item)
        self.assertEqual(item['title'],'Projet de services')
    def test_incomplete_never_becomes_fake_opportunity(self):
        self.assertIsNone(approch.convert({'Code':'45','Date cible de publication':'2027-10-01'}))

if __name__=='__main__':
    unittest.main()
