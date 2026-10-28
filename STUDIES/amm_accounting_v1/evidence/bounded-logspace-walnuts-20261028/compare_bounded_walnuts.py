"""Physical-coordinate comparison to all pre-existing qualified references."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
import pandas as pd

root=Path(sys.argv[1]);catalog=Path(sys.argv[2]);out=Path(sys.argv[3]);out.mkdir(exist_ok=False)
manifests=json.loads(catalog.read_text());inputs={};rows=[]
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read_ref(lane,relative):
 p=Path('/home/ubuntu/lanes')/lane/relative;h=digest(p)
 assert h==manifests[lane][relative]['sha256'];inputs[str(p)]=h
 return pd.read_csv(p,index_col=0)
def failures(s):
 bad=(~np.isfinite(s[['r_hat','ess_bulk','ess_tail']]).all(axis=1))|(s.r_hat>1.01)|(s.ess_bulk<400)|(s.ess_tail<400)
 return s.index[bad].tolist()
for j in range(9):
 p=root/f'job-{j}'/'fit'/'coordinates.csv';inputs[str(p)]=digest(p)
 left=pd.read_csv(p,index_col=0).drop(index='b')
 refs={}
 if j%3==0:
  refs['nuts']=read_ref('bounded-rescaled-20261028',f'run01/job-{j//3}/fit/coordinates.csv').drop(index='b')
  table=read_ref('bounded-centered-slice-20261028',f'comparison/cap-{j//3}.csv')
  refs['slice']=table[[c for c in table.columns if c.startswith('slice_')]].rename(columns=lambda s:s[len('slice_'):])
 else:
  for method in ['nuts','slice']:refs[method]=read_ref('bounded-multi-20261028',f'run01/job-{j}/fit/{method}-coordinates.csv')
 for name,right in refs.items():
  assert list(left.index)==list(right.index)
  table=left.add_prefix('walnuts_').join(right.add_prefix(name+'_'))
  z=(left['mean']-right['mean'])/np.hypot(left.mcse_mean,right.mcse_mean);table['combined_z']=z
  table.to_csv(out/f'fit-{j}-{name}.csv')
  rows.append(dict(index=j,reference=name,walnuts_failed=failures(left),reference_failed=failures(right),max_abs_mean_z=float(abs(z).max()),flags_over_4=z.index[abs(z)>4].tolist()))
r=dict(rows=rows,inputs=inputs,manifest_catalog_sha256=digest(catalog),source_sha256=digest(Path(__file__)),scope='Frozen coordinate-summary comparisons; no simultaneous inference or market claim')
(out/'COMPARISON.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows))
