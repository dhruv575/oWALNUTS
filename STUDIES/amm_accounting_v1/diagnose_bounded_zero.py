"""Read-only, chain-specific geometry audit of the frozen all-zero failures."""
from pathlib import Path
import hashlib,json,sys
import arviz as az
import numpy as np

root=Path(sys.argv[1]);out=Path(sys.argv[2]);rows=[];inputs={}
def record(p):
    with p.open('rb') as f:inputs[str(p)]=hashlib.file_digest(f,'sha256').hexdigest()
def describe(a):
    assert np.isfinite(a).all()
    return dict(zip(['min','p05','median','p95','max'],map(float,np.quantile(a,[0,.05,.5,.95,1]))))
def summarize(j,method,mu,l,beta,z,depth=None):
    a=np.empty_like(z);a[:,:,0]=z[:,:,0]/np.sqrt(1-.95**2)
    for i in range(1,z.shape[-1]):a[:,:,i]=.95*a[:,:,i-1]+z[:,:,i]
    hbar=mu+np.exp(l)*a.mean(axis=-1)
    with np.errstate(divide='ignore'):logabs=np.log(abs(beta))
    for c in range(4):
        finite=np.isfinite(logabs[c])
        row=dict(index=j,cap=[.5,1.,2.][j//3],method=method,chain=c,log_sigma=describe(l[c]),mean_h=describe(hbar[c]),beta=describe(beta[c]),exact_zero_beta=int((~finite).sum()),log_abs_scaled_beta=describe((logabs-.5*hbar)[c,finite]) if finite.any() else None)
        if depth is not None:row['depth_hits']=int(depth[c].sum())
        rows.append(row)
for j in [0,3,6]:
    fit=root/f'job-{j}'/'fit';p=fit/'nuts.nc';record(p)
    data=az.from_netcdf(p);post=data.posterior
    summarize(j,'nuts',post.mu.values,post.log_sigma.values,post.beta.values,post.z.values,data.sample_stats.maxdepth_reached.values)
    data.close();draws=[]
    for c in range(4):
        p=fit/f'slice-{c}.npz';record(p)
        with np.load(p) as f:draws.append(f['draws'])
    a=np.stack(draws);summarize(j,'slice',a[:,:,0],a[:,:,1],a[:,:,2],a[:,:,3:])
result=dict(rows=rows,inputs=inputs,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='Post-hoc geometry diagnosis of all frozen all-zero fits; no new sampling or qualified-reference claim')
with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
for j in [0,3,6]:
 for method in ['nuts','slice']:
    r=[x for x in rows if x['index']==j and x['method']==method]
    print(json.dumps(dict(index=j,method=method,chain_median_h=[x['mean_h']['median'] for x in r],chain_median_log_sigma=[x['log_sigma']['median'] for x in r],chain_median_log_abs_scaled_beta=[x['log_abs_scaled_beta']['median'] if x['log_abs_scaled_beta'] else None for x in r])))
