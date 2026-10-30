import json
from pathlib import Path
import numpy as np
from scipy.stats import norm
root=Path(__file__).resolve().parent;run=root/'mixing01';manifest=json.loads((run/'MANIFEST.json').read_text());rows=[]
for i,j in enumerate(manifest['jobs']):
 x=np.load(run/f'{i:03d}'/'draws.npz')['post_sweep'];k=(x[:,:,0]>0).sum(1)
 rows.append(dict(**j,min_positive=int(k.min()),max_positive=int(k.max()),all_broad_chunks=int((k==0).sum()),all_narrow_chunks=int((k==4).sum())))
p=.8*norm.sf(4)+.2*norm.sf(-40)
conditional=(p-p**4)/(1-(1-p)**4-p**4)
r=dict(rows=rows,conditional_probability_if_one_to_three_positive_walkers=float(conditional),interpretation='Post-hoc mechanism diagnostic. Product target conditional on retaining at least one walker in each sign region. Agreement supports a slow region-occupancy explanation; it does not prove a limiting law or invalidate the invariant-target derivation.')
(root/'OCCUPANCY-AUDIT.json').write_text(json.dumps(r,indent=2)+'\n')
for d in [1,8]:
 for s in ['cold','covered']:
  a=[v for v in rows if v['d']==d and v['start']==s and v['arm']=='ensemble']
  print(d,s,'min',min(v['min_positive'] for v in a),'max',max(v['max_positive'] for v in a),'all_broad_chunks',sum(v['all_broad_chunks'] for v in a),'all_narrow_chunks',sum(v['all_narrow_chunks'] for v in a))
print('conditional probability',conditional)
