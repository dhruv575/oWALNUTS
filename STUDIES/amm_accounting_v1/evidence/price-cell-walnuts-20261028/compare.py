from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
base=Path('STUDIES/amm_accounting_v1/evidence/price-cell-walnuts-20261028')
ref=Path('STUDIES/amm_accounting_v1/evidence/price-cell-slice-v3-20261028/price-cell-slice-long-v3-20261028/comparison01')
rows=[];bindings={}
for i in range(4):
 p=base/f'report01/fixture-{i}-coordinates.csv';r=ref/f'fixture-{i}-coordinates.csv'
 for x in (p,r):bindings[str(x)]=hashlib.sha256(x.read_bytes()).hexdigest()
 w=pd.read_csv(p,index_col=0);s=pd.read_csv(r,index_col=0)
 assert list(w.index)==list(s.index)
 table=w.add_prefix('walnuts_').join(s)
 row=dict(index=i,coordinates=len(w))
 for method in ('nuts','slice'):
  z=(w['mean']-s[method+'_mean'])/np.hypot(w['mcse_mean'],s[method+'_mcse_mean'])
  assert np.isfinite(z).all()
  table['walnuts_vs_'+method+'_z']=z
  row[method]=dict(max_abs_mean_combined_z=float(abs(z).max()),flags_over_4=z.index[abs(z)>4].tolist(),reference_failed_coordinates=s.index[~s[method+'_pass']].tolist())
 table.to_csv(base/f'comparison-{i}.csv');rows.append(row)
r=dict(rows=rows,bindings=bindings,scope='All-coordinate mean comparison; MCSE requires convergence. Slice fixture 1 failed diagnostics. No multiplicity-adjusted fidelity proof or speed advantage claimed.')
(base/'COMPARISON.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
