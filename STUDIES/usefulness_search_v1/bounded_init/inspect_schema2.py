import json
from pathlib import Path
root=Path('/dev/shm/bounded-init-20261030');r=json.loads((root/'preflight01/funnel-bounded/RESULT.json').read_text());print('funnel tail',r['tail_mass'])
m=json.loads((root/'run01/MANIFEST.json').read_text())
for i,job in enumerate(m['jobs']):
 p=root/'run01'/f'{i:03d}'/'RESULT.json'
 if job[0]=='sv' and p.exists():
  r=json.loads(p.read_text());print('sv root',list(r));print('sv chain',list(r['chains_data'][0]));break
