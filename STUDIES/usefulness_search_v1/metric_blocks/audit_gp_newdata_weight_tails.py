import hashlib,json,sys
from pathlib import Path
import numpy as np
root=Path(sys.argv[1]);rows=[]
for scenario in range(4):
 for rep in range(2):
  d=root/f'{scenario}-{rep}';a=np.load(d/'draws.npz');q=a['q'];w=a['weight'];order=np.argsort(w);top=order[-100:];h=np.exp(q[:,:2]);outside=(h[:,0]<.5)|(h[:,0]>20)|(h[:,1]<.1)|(h[:,1]>10)
  masks={'alpha_below_grid':h[:,1]<.1,'alpha_above_grid':h[:,1]>10,'rho_outside_grid':(h[:,0]<.5)|(h[:,0]>20),'outside_any_grid':outside}
  groups={name:dict(proposals=int(mask.sum()),weighted_mass=float(w[mask].sum()),top100=int(mask[top].sum()),max_weight=float(w[mask].max()) if mask.any() else 0) for name,mask in masks.items()}
  rows.append(dict(scenario=scenario,rep=rep,sha256=hashlib.sha256((d/'draws.npz').read_bytes()).hexdigest(),groups=groups,top100_weight=float(w[top].sum()),max_weight=float(w.max()),top100_alpha_range=[float(h[top,1].min()),float(h[top,1].max())]))
result=dict(scope='Post-hoc descriptive attribution of weights; no causal proof or repaired qualification',rows=rows)
(root/'WEIGHT-TAIL-AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
