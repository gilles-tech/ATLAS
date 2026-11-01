"""Fast release gates — no network or private database required."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent

class DistributionTests(unittest.TestCase):
    def test_required_files(self):
        for path in ['app.py', 'desktop.py','desktop_autosync.py','static/index.html','sources.json','packaging/build_macos_release.sh']:
            with self.subTest(path=path):
                self.assertTrue((ROOT/path).is_file(), path)
    def test_no_bundled_database(self):
        for suffix in ('*.db', '*.sqlite', '*.sqlite3'):
            self.assertFalse(list(ROOT.rglob(suffix)), f'Database included: {suffix}')
    def test_data_path_outside_bundle(self):
        self.assertIn("Path.home() / 'AtlasMarches'", (ROOT/'desktop.py').read_text())

if __name__ == '__main__':
    unittest.main()
