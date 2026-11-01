"""Per-user macOS LaunchAgent installation, never requires Terminal or admin rights."""
import os
import plistlib
import subprocess
import sys
from pathlib import Path

LABEL = 'fr.atlasmarches.desktop.sync'


def setup_daily_sync() -> tuple[bool, str]:
    if sys.platform != 'darwin':
        return False, 'La planification automatique intégrée est disponible sur macOS uniquement.'
    # For a PyInstaller .app sys.executable is the bundled Mach-O executable.
    executable = Path(sys.executable).resolve()
    if '.app/Contents/MacOS/' not in str(executable):
        return False, 'Lancez la version AtlasMarches.app installée dans Applications.'
    root = Path.home() / 'AtlasMarches'
    logs = root / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    agents = Path.home() / 'Library' / 'LaunchAgents'
    agents.mkdir(parents=True, exist_ok=True)
    plist = agents / f'{LABEL}.plist'
    payload = {
        'Label': LABEL,
        'ProgramArguments': [str(executable), '--sync'],
        'StartCalendarInterval': {'Hour': 6, 'Minute': 0},
        'StandardOutPath': str(logs / 'desktop-sync.log'),
        'StandardErrorPath': str(logs / 'desktop-sync-error.log'),
        'RunAtLoad': False,
    }
    tmp = plist.with_suffix('.plist.tmp')
    with tmp.open('wb') as fh:
        plistlib.dump(payload, fh)
    os.replace(tmp, plist)
    uid = str(os.getuid())
    subprocess.run(['launchctl', 'bootout', f'gui/{uid}', str(plist)], capture_output=True, check=False)
    result = subprocess.run(['launchctl', 'bootstrap', f'gui/{uid}', str(plist)], capture_output=True, text=True)
    if result.returncode:
        return False, result.stderr.strip() or 'Impossible de planifier la synchronisation.'
    return True, 'Synchronisation quotidienne configurée à 06:00 lorsque la session Mac est disponible.'


def schedule_consent_marker() -> Path:
    root = Path.home() / 'AtlasMarches' / 'data'
    root.mkdir(parents=True, exist_ok=True)
    return root / 'macos-sync-onboarding-v1.txt'


def setup_on_first_launch(window) -> None:
    """Ask once, from the GUI, then configure LaunchAgent only with consent."""
    if sys.platform != 'darwin':
        return
    marker = schedule_consent_marker()
    if marker.exists():
        return
    try:
        # A native webview JS confirmation, user makes the choice inside the app.
        accepted = window.evaluate_js('window.confirm("Atlas peut actualiser automatiquement BOAMP et TED chaque jour à 06:00, même lorsque la fenêtre est fermée (si votre session Mac est ouverte). Activer cette option ?")')
        if accepted:
            ok, message = setup_daily_sync()
            window.evaluate_js(f'window.alert({__import__("json").dumps(message, ensure_ascii=False)})')
            if ok:
                marker.write_text('enabled\n', encoding='utf-8')
        else:
            marker.write_text('declined\n', encoding='utf-8')
    except Exception as exc:
        # Do not block application launch if prompt is unsupported.
        print(f'Optional sync onboarding unavailable: {exc}', file=sys.stderr)
