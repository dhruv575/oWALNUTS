import hashlib,json,tarfile,io
from pathlib import Path
import numpy as np
import pandas as pd
import arviz as az
p=Path('target/price-cell-long-full-20261028.tar.gz')
with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
assert digest=='b3047a7bdbb58b6934f77bc3786d4ff2d583c5e53108481e399ac40c412467c6'
prefix='price-cell-long-20261028/';manifest={};rows=[]
with tarfile.open(p) as t:
 for m in t:
  if not m.isfile():continue
  assert m.name.startswith(prefix)
  raw=t.extractfile(m).read();name=m.name[len(prefix):]
  assert name not in manifest
  manifest[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 for i in range(4):
  base=prefix+f'run01/job-{i}/fit/'
  raw=t.extractfile(base+'trace.nc').read();local=Path(f'target/long-cell-trace-{i}.nc');local.write_bytes(raw)
  trace=az.from_netcdf(local)
  assert trace.posterior.sizes['chain']==4 and trace.posterior.sizes['draw']==4000 and trace.warmup_posterior.sizes['draw']==2000
  actual=az.summary(trace,var_names=['mu','log_sigma','beta','z','u'],round_to='none')
  expected=pd.read_csv(io.BytesIO(t.extractfile(base+'coordinates.csv').read()),index_col=0)
  assert list(actual.index)==list(expected.index)
  np.testing.assert_allclose(actual.to_numpy(),expected.to_numpy(),rtol=1e-9,atol=1e-10)
  direct=int(trace.sample_stats['maxdepth_reached'].sum());div=int(trace.sample_stats['diverging'].sum())
  rows.append(dict(index=i,coordinates=len(actual),summary_reconstructed=True,maxdepth_reached=direct,divergences=div))
  trace.close()
base=Path('STUDIES/amm_accounting_v1/evidence/price-cell-long-20261028')
(base/'FULL-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
result=dict(archive_sha256=digest,bytes=p.stat().st_size,files=len(manifest),rows=rows,scope='Full archive matches remote hash; local summary reconstruction uses same ArviZ estimators')
(base/'ARCHIVE-VERIFIED.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
