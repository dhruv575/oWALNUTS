from pathlib import Path
import sys,json,time,hashlib,random
H=Path(__file__).resolve().parent;R=H.parents[1];S=R/'STUDIES/options_flow_v1';sys.path[:0]=[str(H),str(S)]
from reference_bank_allocation import memory_limit,peak_memory
job=memory_limit(8*1024**3)
import numpy as np
from adaptive_grid import build
from predictive_cdf import PredictiveMixture
out=H/'grid-probe-v1';config=json.loads((out/'config.json').read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert all(sha(p)==h for p,h in config['bindings'].items())
mixtures={};tick=time.perf_counter()
for ident in ['fit-1-reference','fit-2-reference']:
 with np.load(S/f'artifacts/posterior-resource-pilot-v1/{ident}/extracted/compact.npz') as z:
  for n in [4000,8000]:
   count=4*n;mixtures[f'{ident}-{n}']=PredictiveMixture('flow',z['cdf_location'][:,:n].reshape(-1).copy(),z['cdf_future_mean'][:,:n].reshape(-1).copy(),z['cdf_future_sd'][:,:n].reshape(-1).copy(),np.zeros(count),np.full(count,1/count),5.,2048,{})
rng=random.Random(731);weights=[]
for _ in range(30000):
 count=sum(rng.randrange(2)==0 for j in range(2));weights.extend([[count,0,2-count,0],[0,count,0,2-count]])
weights.extend([[1,0,1,0],[0,1,0,1],*np.eye(4,dtype=int).tolist()]);weights=np.asarray(weights,dtype=np.int64)
np.save(out/'frozen-weights.npy',weights)
print(json.dumps(dict(phase='grid',weight_rows=len(weights),weights_sha256=sha(out/'frozen-weights.npy'))),flush=True)
result=build(mixtures,initial=(-1.,3.),max_queries=64,max_rounds=32,absolute_width=.01,cdf_tolerance=1e-8,frozen_weights=weights)
assert all(sha(p)==h for p,h in config['bindings'].items())
result.update(seconds=time.perf_counter()-tick,resources=peak_memory(),config_sha256=sha(out/'config.json'),weights_sha256=sha(out/'frozen-weights.npy'),performance_scope='Saved pilot computational probe only; no new posterior draws or bank accuracy claim.')
with (out/'result.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps({k:result[k] for k in ['status','reason','queries','seconds','declared_weight_brackets_resolved']}),flush=True)
