import json,sys,hashlib
from pathlib import Path
import numpy as np
base=Path('/home/ubuntu/lanes/rolling-market-nutpie-20261028')
sys.path.insert(0,str(base/'source'))
from rolling_market_worker import validate
spec,parent=validate(base/'run01/PLAN.json')
sys.path.insert(0,str(Path(parent['worker_path']).parent));sys.path.append(parent['e62_root']);import data_contract
rows=[]
for m in parent['months']:
 data_contract.configure(m['month']);y=data_contract.load_sealed(parent['acquisition'],m['month'])
 duplicates=[];sentinels=[]
 for tick in range(m['origins']+1):
  w=y[tick:tick+250];values,counts=np.unique(w,return_counts=True)
  repeated=values[counts>1];maximum=int(counts.max())
  if maximum>1:duplicates.append(dict(tick=tick,max_multiplicity=maximum,repeated_values=repeated.tolist(),zero_count=int(np.count_nonzero(w==0))))
  if tick in m['reference_ticks']:sentinels.append(dict(tick=tick,max_multiplicity=maximum,zero_count=int(np.count_nonzero(w==0))))
 rows.append(dict(data_sha256=hashlib.sha256(y.tobytes(order='C')).hexdigest(),all_repeated_values=sorted({v for d in duplicates for v in d['repeated_values']}),month=m['month'],windows=m['origins']+1,duplicate_windows=len(duplicates),max_multiplicity=max((x['max_multiplicity'] for x in duplicates),default=1),examples=duplicates[:3],sentinels=sentinels))
out=base/'EXACT-DUPLICATE-AUDIT-V2.json';out.write_text(json.dumps(dict(scope='Exact float64 equality in existing conditioning windows; no posterior-propriety conclusion by itself',rows=rows),indent=2)+'\n');print(out.read_text())
