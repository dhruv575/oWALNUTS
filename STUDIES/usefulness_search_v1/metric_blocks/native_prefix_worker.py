"""Exposed full-budget prefix and exact continuation-cost qualification."""
import hashlib,json,sys
from pathlib import Path
import numpy as np,nutpie
from native_common import LOCAL,model_files,native_model,counter_handle,counter_read
model=sys.argv[1];root=Path(sys.argv[2]);so,data,source=model_files(model)
shim=LOCAL/'nativemodels01'/model/'counted_model.so';c=counter_handle(shim)
prior=json.loads((LOCAL/'nativemodels01'/model/'BUILD.json').read_text());assert hashlib.sha256(shim.read_bytes()).hexdigest()==prior['shim_sha256']
results={};counts={}
for n in [100,2100]:
    c.ow_reset_target_calls()
    t=nutpie.sample(native_model(shim,data,source),draws=n,tune=1100,chains=4,cores=4,seed=940850001,save_warmup=True,progress_bar=False,adaptation='low_rank',target_accept=.8,maxdepth=10,store_unconstrained=True,store_transformed=True,store_gradient=True,store_mass_matrix=True,mass_matrix_eigval_cutoff=2.,mass_matrix_gamma=1e-5)
    counts[n]=counter_read(c);arrays={}
    for group in ['sample_stats','warmup_sample_stats']:
        for k,v in t[group].data_vars.items():
            a=np.asarray(v.values)
            if a.dtype.kind in 'biuf':arrays[group+'__'+k]=a.copy()
    t.close();np.savez_compressed(root/('short.npz' if n==100 else 'long.npz'),**arrays);results[n]=arrays
short,long=results[100],results[2100]
prefix={k:bool(np.array_equal(a,long[k][:,:100] if k.startswith('sample_stats__') else long[k],equal_nan=True)) for k,a in short.items()}
calls=counts[2100]['gradient']-counts[100]['gradient'];steps=int(long['sample_stats__n_steps'][:,100:].sum())
stable=all(len(np.unique(long['sample_stats__transformation_index'][i]))==1 and len(np.unique(long['sample_stats__step_size'][i]))==1 for i in range(4))
passed=all(prefix.values()) and calls==steps and calls>0 and stable and all(counts[n][k]==0 for n in counts for k in ['value','hessian','hvp'])
out=dict(passed=passed,model=model,seed=940850001,prefix_fields=prefix,counts=counts,continuation_gradient_calls=calls,continuation_steps=steps,fixed_transform_and_step=stable,scope=__doc__,inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),so,shim,data,source]})
(root/'SUMMARY.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(model=model,passed=passed,failed_prefix_fields=[k for k,v in prefix.items() if not v],calls=calls,steps=steps,stable=stable)))
