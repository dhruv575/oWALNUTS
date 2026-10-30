import json
from pathlib import Path
import numpy as np,bridgestan
root=Path(__file__).resolve().parent
source=Path('/dev/shm/bounded-init-20261030/run01/012/RESULT.json')
models=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models');name='hudson_lynx_hare-lotka_volterra'
m=bridgestan.StanModel(str(models/(name+'_model.so')),data=str(models/(name+'.data.json')),seed=1)
x=json.loads(source.read_text());rows=[]
for c in x['chains_data']:
 q=np.array(c['samples']);lp=np.array([m.log_density_gradient(v)[0] for v in q])
 rows.append(dict(first=lp[0],last=lp[-1],median=np.median(lp),min=lp.min(),max=lp.max(),first_q=q[0].tolist(),last_q=q[-1].tolist(),warmup_end=c['warmup_end'],sampling_end=c['sampling_end']))
local=np.load(root/'replay-local/draws.npz');aug=np.load(root/'replay-ensemble/draws.npz')
r=dict(original_density=rows,exact_local_draws=np.array_equal(local['local'],aug['local']),exact_post_sweep=np.array_equal(local['post_sweep'],aug['post_sweep']))
(root/'REPLAY-AUDIT.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
