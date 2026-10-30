import hashlib,json
from pathlib import Path
import numpy as np
root=Path('/dev/shm/bounded-init-20261030');manifest=json.loads((root/'run01/MANIFEST.json').read_text());r={};inputs={}
for i,job in enumerate(manifest['jobs']):
 kind,model,arm,seed=job
 if model=='hudson_lynx_hare-lotka_volterra' and seed==939100003 and arm in ['gradinit','bounded']:
  p=root/'run01'/f'{i:03d}'/'RESULT.json';raw=p.read_bytes();inputs[str(p)]=hashlib.sha256(raw).hexdigest();r[arm]=json.loads(raw)
a,b=r['gradinit'],r['bounded'];assert a['starts']==b['starts'];assert a['target_calls_total']==b['target_calls_total'];assert a['draw_hash']==b['draw_hash']
for c,d in zip(a['chains_data'],b['chains_data']):
 assert c['initial_mass_diagonal']==d['initial_mass_diagonal'];assert np.array_equal(c['samples'],d['samples'])
result=dict(passed=True,exact_samples_and_calls=True,initial_masses_unchanged=True,inputs=inputs,interpretation='Bounds do not activate in the failed Lotka case; extreme initial masses do not explain this failure.')
(root/'LOTKA-PARITY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
