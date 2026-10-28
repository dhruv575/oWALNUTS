"""Recover reporting from preserved draws; never resample."""
import json,sys,hashlib
from pathlib import Path
import numpy as np
import arviz as az

root=Path(sys.argv[1]);out=root/'RECOVERED-REPORT.json'
if out.exists():raise FileExistsError(out)
files=['rejection.npz','nuts.npz','trace.nc']
bindings={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in files}
with np.load(root/'rejection.npz') as f:ref=f['draws']
with np.load(root/'nuts.npz') as f:full=f['draws']
assert full.shape==(4,4000,5) and ref.shape[1]==5
assert np.isfinite(full).all() and np.isfinite(ref).all()
trace=az.from_netcdf(root/'trace.nc');rows=[]
for i,name in enumerate(['mu','log_sigma','beta','z','u']):
 a=full[:,:,i];r=ref[:,i]
 mcse=np.asarray(az.mcse(a,method='mean')).item();se=r.std(ddof=1)/np.sqrt(len(r))
 row=dict(name=name,rhat=np.asarray(az.rhat(a)).item(),ess_bulk=np.asarray(az.ess(a,method='bulk')).item(),ess_tail=np.asarray(az.ess(a,method='tail')).item(),mean=float(a.mean()),mcse=mcse,reference_mean=float(r.mean()),reference_se=float(se),standardized_difference=float((a.mean()-r.mean())/np.hypot(mcse,se)),quantiles=np.quantile(a,[.1,.5,.9]).tolist(),reference_quantiles=np.quantile(r,[.1,.5,.9]).tolist())
 row['diagnostic_pass']=row['rhat']<=1.01 and min(row['ess_bulk'],row['ess_tail'])>=400
 rows.append(row)
divergences=int(trace.sample_stats['diverging'].sum())
result=dict(scope='Recovered reporting only, original sampled evidence unchanged; single T1 synthetic fixture',bindings=bindings,rows=rows,divergences=divergences,diagnostic_pass=divergences==0 and all(r['diagnostic_pass'] for r in rows),mean_disagreement_flags=[r['name'] for r in rows if abs(r['standardized_difference'])>4],source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
with out.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
print(json.dumps(result))
trace.close()
