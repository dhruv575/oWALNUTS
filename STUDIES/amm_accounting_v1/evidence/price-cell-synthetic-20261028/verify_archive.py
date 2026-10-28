import hashlib,json,tarfile,io
from pathlib import Path
import numpy as np
import arviz as az
p=Path('target/price-cell-synthetic-20261028.tar.gz')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='d76cdd046766140ac8bf5d10be64cf3d8a08c74096247acfb79ac735f888b009'
prefix='price-cell-synthetic-20261028/'
with tarfile.open(p) as t:
 files={m.name[len(prefix):]:t.extractfile(m).read() for m in t if m.isfile() and m.name.startswith(prefix)}
report=json.loads(files['run01/fit/RECOVERED-REPORT.json']);plan=json.loads(files['run01/PLAN.json'])
for name,h in plan['sources'].items():assert hashlib.sha256(files[name]).hexdigest()==h
for name,h in report['bindings'].items():assert hashlib.sha256(files['run01/fit/'+name]).hexdigest()==h
with np.load(io.BytesIO(files['run01/fit/nuts.npz'])) as f:draws=f['draws']
with np.load(io.BytesIO(files['run01/fit/rejection.npz'])) as f:ref=f['draws']
tracepath=Path('target/price-cell-verified-trace.nc');tracepath.write_bytes(files['run01/fit/trace.nc'])
trace=az.from_netcdf(tracepath)
assert trace.warmup_posterior.sizes['draw']==2000
for i,row in enumerate(report['rows']):
 name=row['name'];a=draws[:,:,i];r=ref[:,i]
 actual=np.asarray(trace.posterior[name].transpose('chain','draw',...)).reshape(4,4000,-1)[:,:,0]
 assert np.array_equal(a,actual)
 assert np.isclose(a.mean(),row['mean'],rtol=0,atol=1e-14)
 assert np.isclose(r.mean(),row['reference_mean'],rtol=0,atol=1e-14)
 assert np.isclose(np.asarray(az.rhat(a)).item(),row['rhat'],rtol=1e-12)
 assert np.isclose(np.asarray(az.mcse(a)).item(),row['mcse'],rtol=1e-12)
assert int(trace.sample_stats.diverging.sum())==report['divergences']==0
trace.close()
result=dict(archive_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size,files=len(files),source_bindings_verified=True,draw_bindings_verified=True,trace_draw_identity_verified=True,warmup_draws=2000,rejection_draws=len(ref),nuts_shape=list(draws.shape),means_rhat_mcse_reconstructed=True,scope='Off-instance reconstruction with same ArviZ estimator; not an independent diagnostic implementation')
base=Path('STUDIES/amm_accounting_v1/evidence/price-cell-synthetic-20261028')
(base/'ARCHIVE-VERIFIED.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
