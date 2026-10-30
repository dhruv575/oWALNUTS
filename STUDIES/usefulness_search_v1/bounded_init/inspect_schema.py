import json
from pathlib import Path
root=Path('/dev/shm/bounded-init-20261030')
for p in [root/'preflight01/pdb-bounded/RESULT.json',root/'preflight01/funnel-bounded/RESULT.json']:
 r=json.loads(p.read_text());print(p.name,p.parent.name);print('root keys',list(r));print('chain keys',list(r['chains_data'][0]));print('work', {k:v for k,v in r['chains_data'][0].items() if 'work' in k or k in ['warmup_target_calls','tail_mass']})
print((root/'run01/STATUS.json').read_text() if (root/'run01/STATUS.json').exists() else 'No completions yet')
