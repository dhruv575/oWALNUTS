from pathlib import Path
import sys,json,time,random,hashlib
import numpy as np
H=Path(__file__).resolve().parent;R=H.parents[1];S=R/'STUDIES/options_flow_v1';sys.path.insert(0,str(S))
from predictive_cdf import PredictiveMixture
from reference_bank import prepare_parameters
from reference_bank_vectorized import batch_cached_parameter
P=S/'artifacts/posterior-resource-pilot-v1';names=['beta_bar','tau','mu_h','sigma_h','h_terminal'];fits=[];timings=[];bindings={}
for ident in ['fit-1-reference','fit-2-reference']:
 path=P/ident/'extracted/compact.npz';bindings[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
 with np.load(path) as z:arrays={k:z[k] for k in z.files}
 fit=dict(id=ident,levels={})
 for n in [4000,8000]:
  fit['levels'][str(n)]=dict(endpoints={k:dict(draws=arrays[k][:,:n].reshape(-1).tolist()) for k in names})
  count=4*n;mix=PredictiveMixture('flow',arrays['cdf_location'][:,:n].reshape(-1),arrays['cdf_future_mean'][:,:n].reshape(-1),arrays['cdf_future_sd'][:,:n].reshape(-1),np.zeros(count),np.full(count,1/count),5.,2048,{})
  # Same five querypoints across fits/prefixes; resource-only, not sufficient inversion grid.
  grid=np.array([-.3,-.15,.7,1.6,1.8]);results={}
  for order in [64,128]:
   tick=time.perf_counter();v=mix.cdf(grid,order=order);seconds=time.perf_counter()-tick;results[str(order)]=v.tolist();timings.append(dict(fit=ident,draws=n,queries=5,order=order,seconds=seconds))
  fit['cdf_probe']=results
 fits.append(fit)
spec=dict(lengths=[4000,8000],endpoints={k:dict(kind='parameter',distribution_id=k) for k in names})
tick=time.perf_counter();cache=prepare_parameters(fits,spec);setup=time.perf_counter()-tick
rng=random.Random(731);counts=[]
for _ in range(2048):
 chosen=[rng.randrange(2) for i in range(2)];counts.append({fits[i]['id']:chosen.count(i) for i in range(2)})
tick=time.perf_counter()
for n in [4000,8000]:
 for k in names:
  for q in [.05,.95]:batch_cached_parameter(fits,cache,n,k,q,counts)
bootstrap=time.perf_counter()-tick
out=dict(scope='Resource-only existing two reference pilot fits. No bank uncertainty/accuracy inference, no independent posterior fits generated.',bindings=bindings,cdf_queries=timings,parameter_cache_setup_seconds=setup,parameter20endpointprefix_evaluations_2048resamples_seconds=bootstrap,predictive_grid_adequate_for_bank=False,mixed_family_batch_routing_supported=False,qualified=False)
with (H/'saved-data-resource-probe-v1.json').open('x') as f:json.dump(out,f,indent=2)
print(json.dumps(out))
