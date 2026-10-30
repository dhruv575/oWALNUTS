import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
import arviz as az
from scipy.special import ndtr
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'native_recycling_test02'
s=json.loads((r/'SUMMARY.json').read_text());assert s['passed']
for name,h in s['inputs'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
rows=[]
for row in s['rows']:
    stem=row['target']+'-'+row['adaptation'];arms=[json.loads((r/(stem+'-'+a)/'RAW.json').read_text()) for a in ['pristine','disabled','enabled']]
    for triple in zip(*(a['chains'] for a in arms)):
        cleaned=[{k:v for k,v in c.items() if k not in ('seconds','recycled')} for c in triple];assert cleaned[0]==cleaned[1]==cleaned[2]
        assert not triple[0]['recycled'] and not triple[1]['recycled']
    x=np.array([c['all_draws'][1000:] for c in arms[2]['chains']]);v=np.array([c['recycled'][1000:] for c in arms[2]['chains']]);d=x.shape[-1]
    assert np.isfinite(v).all() and v.shape==(4,4000,4*d)
    assert v[:,:,2*d:].min()>=0 and v[:,:,2*d:].max()<=1+1e-14
    assert (v[:,:,d:2*d]-v[:,:,:d]**2).min()>-1e-9
    if row['target']!='funnel':
        var=np.array([2.,2.] if d==2 else [9.]+[1.]*9)
        truth=np.r_[np.zeros(d),var,np.full(d,.5),ndtr(-2/np.sqrt(var))]
        tol=np.r_[.05*np.sqrt(var),.05*var,np.full(2*d,.01)]
        assert np.all(abs(v.mean((0,1))-truth)<=tol)
        assert all(float(az.rhat(x[:,:,i]))<=1.01 and min(float(az.ess(x[:,:,i],method=m)) for m in ['bulk','tail'])>=400 for i in range(d))
        assert row['retained_divergences']==0
    rows.append(dict(target=row['target'],adaptation=row['adaptation'],parity=True,retained_divergences=row['retained_divergences'],gaussian_qualified=row.get('gaussian_qualified')))
(p/'NATIVE-RECYCLING-REPLAY.json').write_text(json.dumps(dict(passed=True,rows=rows,scope='Independent raw replay; Gaussian qualification, funnel parity only; no efficacy claim'),indent=2)+'\n')
files={}
for name in ['native_pristine_source01','native_recycling_source01','native_recycling_build01','native_recycling_build02','native_recycling_test01','native_recycling_test02']:
    for f in (l/name).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for name in ['native_pristine_runner','native_recycling_runner']:
    for f in (p/name).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for pattern in ['*native_recycling*.py','*native_preflight*.py','repair_native_workspace.py','native_recycling_main.rs','NATIVE-RECYCLING-*']:
    for f in p.glob(pattern):
        if f.is_file():files[f.name]=f
for name,b in s['binaries'].items():
    f=Path(b['binary']);assert hashlib.sha256(f.read_bytes()).hexdigest()==b['binary_sha256'];files['binary/'+name]=f
out=l/'native_recycling_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz'
manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local source, binaries and successful/failed evidence; not off-device backup')
(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
