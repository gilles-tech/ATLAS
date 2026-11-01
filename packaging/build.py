"""Build a portable standalone app on the current operating system."""
from pathlib import Path
import subprocess
import sys
import platform

root = Path(__file__).resolve().parent.parent
sep = ';' if platform.system() == 'Windows' else ':'
cmd = [sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm',
       '--windowed', '--onedir', '--name', 'AtlasMarches',
       '--collect-all', 'webview',
       '--distpath', str(root / 'dist'), '--workpath', str(root / 'build'),
       '--specpath', str(root),
       '--add-data', f'{root / "static"}{sep}static']
for name in ['sources.json','buyers.json','feeds.json','access_registry.json']:
    cmd.extend(['--add-data', f'{root / name}{sep}.'])
cmd.extend(['--hidden-import', 'desktop_autosync', '--hidden-import', 'standalone_check', '--hidden-import', 'maintenance', '--hidden-import', 'sync_engine'])
cmd.extend(['--hidden-import', 'ted_collector', '--hidden-import', 'collector_runtime'])
cmd.append(str(root / 'desktop.py'))
print('Building on', platform.platform(), flush=True)
subprocess.check_call(cmd, cwd=root)
print('Built:', root / 'dist' / 'AtlasMarches')
