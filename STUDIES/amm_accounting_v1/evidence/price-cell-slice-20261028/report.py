import json,hashlib,tarfile,io
from pathlib import Path
import numpy as np
import arviz as az
p=Path('target/price-cell-slice-20261028.tar.gz');rows=[]
with tarfile.open(p) as t:
 prefix='price-cell-slice-20261028/run01/'
 supervision=json.loads(t.extractfile(prefix+'SUPERVISION.json').read());assert supervision['group_drained'] and supervision['exit_code']==0
 arrays=[];hashes=[]
 for i in range(4):
  raw=t.extractfile(prefix+f'job-{i}/fit/draws.npz').read();hashes.append(hashlib.sha256(raw).hexdigest())
  with np.load(io.BytesIO(raw)) as f:
   assert f['draws'].shape==(4000,5) and f['warmup'].shape==(1000,5);arrays.append(f['draws'])
 with tarfile.open('target/price-cell-synthetic-20261028.tar.gz') as refarchive:
  raw=refarchive.extractfile('price-cell-synthetic-20261028/run01/fit/rejection.npz').read()
  assert hashlib.sha256(raw).hexdigest()=='950b4e3f078ccb1d476906913640c4852b34f48af758a3b9d12f33bf588bba4b'
  with np.load(io.BytesIO(raw)) as f:reference=f['draws']
 a=np.stack(arrays)
 for i,name in enumerate(['mu','log_sigma','beta','z','u']):
  v=a[:,:,i];r=reference[:,i];mcse=np.asarray(az.mcse(v)).item();se=r.std(ddof=1)/np.sqrt(len(r))
  row=dict(name=name,rhat=np.asarray(az.rhat(v)).item(),ess_bulk=np.asarray(az.ess(v,method='bulk')).item(),ess_tail=np.asarray(az.ess(v,method='tail')).item(),mean=float(v.mean()),reference_mean=float(r.mean()),mcse=mcse,standardized_difference=float((v.mean()-r.mean())/np.hypot(mcse,se)))
  row['pass']=row['rhat']<=1.01 and min(row['ess_bulk'],row['ess_tail'])>=400 and abs(row['standardized_difference'])<=4;rows.append(row)
out=Path('STUDIES/amm_accounting_v1/evidence/price-cell-slice-20261028');out.mkdir(exist_ok=False)
with tarfile.open(p) as t:t.extractall(out,filter='data')
result=dict(archive_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),draw_sha256=hashes,rows=rows,scope='Independent transition T1 preflight only')
(out/'COMPARISON.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
