#!/bin/bash
cd "$(dirname "$0")"
python3 - <<'PY'
from pathlib import Path
import json,datetime,subprocess,os
p=Path.home()/'AtlasMarches/data/sync-status.json'
print('ATLAS — ÉTAT DE LA COLLECTE')
if p.exists():
 try:
  d=json.loads(p.read_text());print('Début :',d.get('started'));print('Fin :',d.get('finished'));print('État :',d.get('status'));print('Avant :',d.get('before',{}).get('total'));print('Après :',d.get('after',{}).get('total'));print('Nouveaux IDs :',d.get('new_unique_records'))
  for name,val in d.get('sources',{}).items():print(name,':',val.get('status'), 'détails:',str(val.get('error') or val.get('result',''))[:350])
 except Exception as e:print('Rapport illisible:',e)
else:print('Aucun rapport : synchronisation non encore exécutée ou installation absente')
r=subprocess.run(['launchctl','print',f'gui/{os.getuid()}/fr.atlasmarches.daily-sync'],capture_output=True,text=True)
print('Ordonnanceur macOS :','installé' if r.returncode==0 else 'NON INSTALLÉ')
print('Journal :',Path.home()/'AtlasMarches/logs/daily-sync-error.log')
PY
printf '\nAppuyez sur Entrée pour fermer...'; read -r _
