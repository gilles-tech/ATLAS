"""Validate the actual built installer contains the recovered runtime and no DB."""
import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parent


class InstallerRecoveryTests(unittest.TestCase):
    def test_build_resources_permissions_and_metadata(self):
        spec = importlib.util.spec_from_file_location('atlas_installer_builder',
                        ROOT/'packaging/build_collector_installer.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as directory:
            path = builder.build(Path(directory)/'installer.zip')
            with zipfile.ZipFile(path) as archive:
                prefix = 'Installer Atlas Collector.app/Contents/'
                metadata = plistlib.loads(archive.read(prefix+'Info.plist'))
                self.assertEqual(metadata['CFBundleExecutable'], 'start')
                self.assertEqual(archive.getinfo(prefix+'MacOS/start').external_attr >> 16 & 0o111, 0o111)
                for name in ['collector_runtime.py', 'ted_collector.py', 'sync_engine.py',
                             'sync_daily.py', 'app.py', 'maintenance.py', 'ted_check.py', 'static/index.html']:
                    self.assertEqual(archive.read(prefix+'Resources/'+name), (ROOT/name).read_bytes())
                self.assertFalse(any(name.endswith(('.db','.sqlite','.sqlite3','-wal','-shm'))
                                     for name in archive.namelist()))


if __name__ == '__main__': unittest.main()
