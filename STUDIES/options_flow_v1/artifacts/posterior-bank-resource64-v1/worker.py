"""64-shaped computational control: copied/transformed pilot draws, NOT independent fits."""
from pathlib import Path
import sys,json,time,hashlib
H=Path(__file__).resolve().parent;R=H.parents[1];S=R/'STUDIES/options_flow_v1';sys.path.insert(0,str(S))
from reference_bank_allocation import memory_limit,peak_memory
job=memory_limit(8*1024**3)
import numpy as np
from reference_bank import analyze
from reference_bank_vectorized import batch_cached_parameter
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
config=json.loads((H/'config.json').read_text());assert all(sha(p)==h for p,h in config['bindings'].items());tick=time.perf_counter()
P=S/'artifacts/posterior-resource-pilot-v1';saved=[]
for ident in ['fit-1-reference','fit-2-reference']:
 with np.load(P/ident/'extracted/compact.npz') as z:saved.append({k:z[k].copy() for k in config['parameters']})
grid=json.loads(Path(config['grid_result']).read_text());fits=[];endpoints={};pairs=[]
for name in config['parameters']+['observed_group0_h1']:
 pair=[]
 for label,prob in [('lo',.05),('hi',.95)]:
  key=name+'_'+label;pair.append(key);endpoints[key]=dict(kind='predictive' if name=='observed_group0_h1' else 'parameter',probability=prob,scale='model',distribution_id=name)
 pairs.append(pair)
for i in range(64):
 fit=dict(id=f'COPY-NOT-INDEPENDENT-{i}',backend='a' if i<32 else 'b',seed=100+i,initialization_seed=1000+i,fixture_sha256='computational-copy',source_sha256='resource-only',target_sha256='not-a-posterior-bank',levels={})
 for n in [4000,8000]:
  rows={}
  for name in config['parameters']:
   values=(saved[i%2][name][:,:n]+(i-31.5)*1e-6).reshape(-1).tolist();row=dict(scale='model',distribution_id=name,draws=values)
   rows[name+'_lo']=row;rows[name+'_hi']=row
  source=grid['rows'][f'fit-{1+i%2}-reference-{n}'];row=dict(source,scale='model',distribution_id='observed_group0_h1')
  rows['observed_group0_h1_lo']=row;rows['observed_group0_h1_hi']=row
  fit['levels'][str(n)]=dict(status='completed',healthy=True,draws_per_chain=n,endpoints=rows)
 fits.append(fit)
setup=time.perf_counter()-tick;print(json.dumps(dict(phase='analysis',input_setup_seconds=setup)),flush=True)
spec=dict(fits=[{k:v for k,v in f.items() if k!='levels'} for f in fits],source_sha256='resource-only',target_sha256='not-a-posterior-bank',lengths=[4000,8000],chains=4,endpoints=endpoints,interval_pairs=pairs,numerical_policy='validated_estimate',candidate_streams=[],bootstrap_replicates=30000,minimum_tail_count=20,bootstrap_seed=731,alpha=.05,relative_half_width=.001,backend_equivalence_relative_width=.001,length_equivalence_relative_width=.001)
# Internal healthy labels are schema placeholders for a computational workload,
# never evidence that copies are independent posterior fits. Discard inferential output.
call_times=[]
def timed_batch(*args,**kwargs):
 t=time.perf_counter();value=batch_cached_parameter(*args,**kwargs);call_times.append(time.perf_counter()-t);return value
start=time.perf_counter();result=analyze(spec,fits,parameter_batch=timed_batch);elapsed=time.perf_counter()-start
assert all(sha(p)==h for p,h in config['bindings'].items())
summary=dict(scope='COMPUTATIONAL ONLY:64 deterministic copies/transforms of TWO pilot fits; no independent bank or accuracy result',input_setup_seconds=setup,analysis_seconds=elapsed,parameter_batch_calls=len(call_times),parameter_batch_seconds=sum(call_times),other_analysis_seconds=elapsed-sum(call_times),full_30000_bootstrap_rows_produced=len(result.get('joint_bootstrap_endpoints',[])),resources=peak_memory(),config_sha256=sha(H/'config.json'),qualified=False,statistical_results_deliberately_not_reported=True)
with (H/'result.json').open('x') as f:json.dump(summary,f,indent=2)
print(json.dumps(summary),flush=True)
