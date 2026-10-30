import json
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parent;rows=[]
for version in ['replay','replay-v2']:
 for arm in ['local','ensemble']:
  p=root/(version+'-'+arm);x=np.load(p/'draws.npz');r=json.loads((p/'RESULT.json').read_text())
  # A disclosed descriptive density-region threshold, not a mode label or truth.
  low=x['log_density'][:,1]<-35
  rows.append(dict(version=version,arm=arm,chain1_low_density_chunks=int(low.sum()),first_chain1_chunk_above_minus35=int(np.flatnonzero(~low)[0])+1 if (~low).any() else None,accepted=sum(r['accepted']),calls=r['calls'],seconds=r['seconds']))
r=dict(rows=rows,threshold=-35,interpretation='Post-hoc descriptive density region only; no inferred mode probability, convergence or efficacy claim.')
(root/'REPLAY-SUMMARY.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
