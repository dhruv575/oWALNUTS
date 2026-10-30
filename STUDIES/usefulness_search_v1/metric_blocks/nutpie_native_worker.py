"""Pinned native baseline worker; does not invent a complete gradient count."""
import hashlib,importlib.metadata,json,platform,sys,time
from pathlib import Path
import numpy as np
import nutpie
from nutpie import _lib
from nutpie.compile_stan import CompiledStanModel

inp=json.loads(Path(sys.argv[1]).read_text());out=Path(sys.argv[2]);root=out.parent
assert importlib.metadata.version('nutpie')=='0.16.11'
paths={k:Path(inp[k]) for k in ['model','data','source']}
library=_lib.StanLibrary(str(paths['model']))
compiled=CompiledStanModel(code=paths['source'].read_text(),library=library,dims=None,_coords=None,model=None,data=None).with_data(**json.loads(paths['data'].read_text()))
assert compiled.n_dim==inp['dimension']
kwargs=dict(draws=2000,tune=1100,chains=4,cores=4,seed=inp['seed'],save_warmup=True,progress_bar=False,adaptation=inp['adaptation'],target_accept=.8,maxdepth=10,store_unconstrained=True)
if inp['adaptation']=='low_rank':kwargs.update(mass_matrix_eigval_cutoff=2.,mass_matrix_gamma=1e-5)
(root/'SETTINGS.json').write_text(json.dumps(kwargs,indent=2)+'\n')
start=time.perf_counter();trace=nutpie.sample(compiled,**kwargs);seconds=time.perf_counter()-start
stats=trace['sample_stats'];q=np.asarray(stats['unconstrained_draw'].values)
assert q.shape==(4,2000,inp['dimension']) and np.isfinite(q).all()
saved={};metadata={}
for group in ['sample_stats','warmup_sample_stats']:
    ds=trace[group]
    if hasattr(ds,'to_dataset'):ds=ds.to_dataset()
    metadata[group]={}
    for name,v in ds.data_vars.items():
        a=np.asarray(v.values);metadata[group][name]=dict(shape=list(a.shape),dtype=str(a.dtype))
        if name!='unconstrained_draw' and a.dtype.kind in 'biuf':saved[group+'__'+name]=a
np.savez_compressed(root/'NATIVE-STATS.npz',**saved)
(root/'VARIABLES.json').write_text(json.dumps(metadata,indent=2)+'\n')
result=dict(draws=q.tolist(),retained_divergences=int(np.asarray(stats['diverging']).sum()),native_sampling_and_conversion_seconds=seconds,target_calls=None,target_call_scope='Not instrumented. Native step diagnostics are not a full target-call count.',native_version=importlib.metadata.version('nutpie'))
out.write_text(json.dumps(result,allow_nan=False)+'\n')
environment=dict(python=sys.version,platform=platform.platform(),packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()},sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*paths.values(),Path(__file__),Path(_lib.__file__)]})
(root/'ENVIRONMENT.json').write_text(json.dumps(environment,indent=2)+'\n')
trace.close()
