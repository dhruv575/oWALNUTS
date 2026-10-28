from pathlib import Path
import hashlib,json,tarfile,io
import numpy as np
import pandas as pd
import arviz as az
p=Path('target/bounded-rescaled-full.tar.gz')
with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
assert h=='5d7919aed5de70f8f1452caced7d1f4bd162e6aa53e8a98c8a9c36dbaa2c9c3c'
base=Path('STUDIES/amm_accounting_v1/evidence/bounded-rescaled-20261028');base.mkdir(exist_ok=False)
prefix='bounded-rescaled-20261028/';files={};manifest={}
with tarfile.open(p) as t:
 for m in t:
  if not m.isfile():continue
  assert m.name.startswith(prefix)
  name=m.name[len(prefix):];raw=t.extractfile(m).read();manifest[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
  if name.endswith('.nc'):
   dest=Path('target/bounded-rescaled-verified')/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
  if '/__pycache__/' in name or '/runtime-cache/' in name or name.endswith(('.nc','.so','.hpp','.o')):continue
  dest=base/name;assert dest.resolve().is_relative_to(base.resolve());dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);files[name]=raw
for receipt in ['STAN-COMPARISON.json','run01/PLAN.json']:
 r=json.loads(files[receipt])
 for name,digest in r['sources'].items():assert manifest[name]['sha256']==digest
for j in range(3):
 root=f'run01/job-{j}/fit/';data=az.from_netcdf(Path('target/bounded-rescaled-verified')/root/'nuts.nc')
 assert data.posterior.mu.shape==(4,4000) and data.warmup_posterior.mu.shape==(4,2000)
 for name in ['mu','log_sigma','beta','z','b','h']:assert np.isfinite(data.posterior[name].values).all()
 s=az.summary(data,var_names=['mu','log_sigma','beta','z','b'],round_to='none')
 old=pd.read_csv(io.BytesIO(files[root+'coordinates.csv']),index_col=0)
 np.testing.assert_allclose(s.to_numpy(),old.to_numpy(),rtol=1e-9,atol=1e-10)
 assert (s.r_hat<=1.01).all() and (s.ess_bulk>=400).all() and (s.ess_tail>=400).all()
 assert int(data.sample_stats.diverging.sum())==0 and int(data.sample_stats.maxdepth_reached.sum())==0
 data.close()
outer=json.loads(files['run01/SUPERVISION.json']);assert outer['sources_unchanged'] and outer['group_drained'] and outer['exit_code']==0
(base/'.gitattributes').write_text('* -text\n')
(base/'FULL-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
r=dict(sha256=h,bytes=p.stat().st_size,files=len(manifest),sources_verified=True,raw_nuts_diagnostics_recomputed=True,all_three_fit_diagnostics_pass=True)
(base/'ARCHIVE-VERIFIED.json').write_text(json.dumps(r,indent=2)+'\n');(base/'verify_archive.py').write_bytes(Path(__file__).read_bytes());print(r)
