import json
from pathlib import Path
import numpy as np
ROOT=Path('/dev/shm/bounded-init-20261030');m=json.loads((ROOT/'run01/MANIFEST.json').read_text());rows=[]
for i,(kind,model,arm,seed) in enumerate(m['jobs']):
 if model!='hudson_lynx_hare-lotka_volterra' or seed!=939100003:continue
 p=ROOT/'run01'/f'{i:03d}'/'RESULT.json';r=json.loads(p.read_text());q=np.asarray([c['samples'] for c in r['chains_data']]);sd=q.std(axis=1)
 rows.append(dict(arm=arm,source=str(p),starts=r['starts'],warnings=r['chain_warnings'],chains=[dict(chain=i,mean=q[i].mean(0).tolist(),sd=sd[i].tolist(),final_step=c['final_step_size'],step99=c['step_at_transition_99'],initial_mass=c['initial_mass_diagonal'],final_mass=c['mass_diagonal'],warmup_end=c['warmup_end'],sampling_end=c['sampling_end'],guard=c['trapped_chain_checks'],warmup_calls=c['warmup_target_calls'],retained_calls=c['retained_target_calls'],recoverable=c['recoverable_failures'],step_trace=c['warmup_step_trace_every_50']) for i,c in enumerate(r['chains_data'])]))
(ROOT/'LOTKA-MECHANISM.json').write_text(json.dumps(rows,indent=2)+'\n')
for r in rows:
 print(r['arm'])
 for c in r['chains']:print('chain',c['chain'],'finalstep',c['final_step'],'step99',c['step99'],'warmup_end',c['warmup_end'],'sd',c['sd'],'guard',c['guard'])
