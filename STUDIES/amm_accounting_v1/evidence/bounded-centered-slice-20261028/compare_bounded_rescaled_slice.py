"""Compare every fixed independent control against frozen NUTS physical draws."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
import pandas as pd
import arviz as az

root=Path(sys.argv[1]);ref=Path(sys.argv[2]);manifest=json.loads(Path(sys.argv[3]).read_text());out=Path(sys.argv[4]);out.mkdir(exist_ok=False)
rows=[];inputs={}
def bind(p):
 with p.open('rb') as f:inputs[str(p)]=hashlib.file_digest(f,'sha256').hexdigest()
 return inputs[str(p)]
for j in range(3):
 arrays=[]
 for c in range(4):
  p=root/f'job-{4*j+c}'/'fit'/'draws.npz';bind(p)
  with np.load(p) as f:arrays.append(f['draws'])
 a=np.stack(arrays);assert a.shape==(4,4000,15) and np.isfinite(a).all()
 left=az.summary(az.from_dict(posterior=dict(mu=a[:,:,0],log_sigma=a[:,:,1],beta=a[:,:,2],z=a[:,:,3:])),round_to='none')
 name=f'run01/job-{j}/fit/nuts.nc';p=ref/name
 assert bind(p)==manifest[name]['sha256']
 data=az.from_netcdf(p);right=az.summary(data,var_names=['mu','log_sigma','beta','z'],round_to='none');data.close()
 assert list(left.index)==list(right.index)
 table=left.add_prefix('slice_').join(right.add_prefix('nuts_'));table['combined_z']=(left['mean']-right['mean'])/np.hypot(left.mcse_mean,right.mcse_mean)
 table.to_csv(out/f'cap-{j}.csv');methods={}
 for name,s in [('slice',left),('nuts',right)]:
  bad=(~np.isfinite(s[['r_hat','ess_bulk','ess_tail']]).all(axis=1))|(s.r_hat>1.01)|(s.ess_bulk<400)|(s.ess_tail<400)
  methods[name]=dict(failed_coordinates=s.index[bad].tolist())
 rows.append(dict(cap=[.5,1.,2.][j],methods=methods,max_abs_mean_z=float(abs(table.combined_z).max()),flags_over_4=table.index[abs(table.combined_z)>4].tolist()))
r=dict(rows=rows,inputs=inputs,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),reference_manifest_sha256=bind(Path(sys.argv[3])),scope='All fixed independent-control cases; failed diagnostics preclude reference qualification')
(out/'COMPARISON.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows))
