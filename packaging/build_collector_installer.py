"""Build the script-based macOS collector installer ZIP, without activating it.

This is NOT a standalone Python runtime, signed native app, or notarized DMG.
"""
from pathlib import Path
import plistlib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ['app.py', 'sync_daily.py', 'sync_engine.py', 'collector_runtime.py',
         'ted_collector.py', 'maintenance.py', 'ted_check.py', 'approch.py', 'eu_ft.py',
         'sources.json', 'buyers.json', 'feeds.json', 'access_registry.json',
         'install.sh', 'RECOVERY.md']


def build(destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    prefix = 'Installer Atlas Collector.app/Contents/'
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        def add(name, data, executable=False):
            entry = zipfile.ZipInfo(prefix + name)
            entry.create_system = 3
            entry.external_attr = (0o100755 if executable else 0o100644) << 16
            archive.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED)
        add('Info.plist', plistlib.dumps({'CFBundleIdentifier': 'fr.atlasmarches.collector.installer',
            'CFBundleName': 'Installer Atlas Collector', 'CFBundleExecutable': 'start',
            'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1.1',
            'CFBundleShortVersionString': '1.1', 'LSUIElement': False}))
        add('MacOS/start', (ROOT/'packaging/installer-start.sh').read_bytes(), executable=True)
        for name in FILES:
            add('Resources/'+name, (ROOT/name).read_bytes(), executable=name=='install.sh')
        for path in sorted((ROOT/'static').rglob('*')):
            if path.is_file(): add('Resources/'+str(path.relative_to(ROOT)), path.read_bytes())
    return destination


if __name__ == '__main__':
    print(build(ROOT/'release/Atlas-Collector-Recovery-v1-macOS-unsigned.zip'))
