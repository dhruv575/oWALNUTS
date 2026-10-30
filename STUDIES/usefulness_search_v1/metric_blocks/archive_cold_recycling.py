import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';root=l/'cold_recycling_test01';s=json.loads((root/'SUMMARY.json').read_text());assert s['passed']
for f,h in s['inputs'].items():assert hashlib.sha256(Path(f).read_bytes()).hexdigest()==h
exact=json.loads((l/'banana_recycling_test01/EXACT-CONTROL.json').read_text());truth=np.array(exact['truth']);tol=np.array(exact['tolerances'])
for row in s['rows']:
    prefix=row['target']+'-'+row['metric'];arms=[json.loads((root/(prefix+'-'+a)/'RAW.json').read_text()) for a in ['original','disabled','enabled']];full=json.loads((root/(prefix+'-full')/'RAW.json').read_text());means=[];ordinary=[]
    for a,b,c,f in zip(*(r['chains'] for r in arms),full['chains']):
        for k in a:
            if k not in ['seconds','summary']:assert a[k]==b[k]==c[k]
        x=np.array(f['draws'],dtype='<f8');v=np.array(f['recycled']);assert len(x)==len(v)==4000 and c['summary']['count']==4000;assert hashlib.sha256(x.tobytes()).hexdigest()==c['draw_sha256']
        if row['target']=='banana_latent':x[:,1::2]+=5*(x[:,::2]**2-1)
        obs=np.concatenate([x,x*x,(x<0).astype(float),(x< -2).astype(float)],axis=1);np.testing.assert_allclose(a['summary']['mean'],obs.mean(0),rtol=2e-13,atol=1e-10);np.testing.assert_allclose(c['summary']['mean'],v.mean(0),rtol=2e-13,atol=1e-10);np.testing.assert_allclose(c['summary']['block_means'],v.reshape(80,50,-1).mean(1),rtol=2e-13,atol=1e-10);means.append(v.mean(0));ordinary.append(obs.mean(0))
    if row['target']=='banana_latent':assert np.all(abs(np.mean(means,0)-truth)<=tol) and np.all(abs(np.mean(ordinary,0)-truth)<=tol)
for f in (l/'banana_wal_source01').rglob('*'):
    if f.is_file() and str(f.relative_to(l/'banana_wal_source01')) not in ['src/recycling.rs','src/walnutpie.rs']:assert f.read_bytes()==(l/'cold_wal_source01'/f.relative_to(l/'banana_wal_source01')).read_bytes()
(p/'COLD-RECYCLING-REPLAY.json').write_text(json.dumps(dict(passed=True,scope='Independent raw retained hash, metadata/work parity, retained-only summaries and exact latent moment replay; no efficacy claim'),indent=2)+'\n')
files={}
for name in ['cold_wal_source01','cold_recycling_build01','cold_recycling_build02','cold_recycling_build03','cold_recycling_test01']:
    for f in (l/name).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for name in s['binaries']:
    for f in (p/name).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for pattern in ['*cold_recycling*.py','repair_cold_*.py','COLD-RECYCLING-*','banana_core.rs']:
    for f in p.glob(pattern):
        if f.is_file():files[f.name]=f
for name in ['banana_recycling_archive01','native_recycling_archive01','compact_validation_archive01']:
    f=l/name/'VERIFICATION.json';files[str(f.relative_to(p))]=f
files['local_recovery/banana_recycling_test01/EXACT-CONTROL.json']=l/'banana_recycling_test01/EXACT-CONTROL.json'
for name,b in s['binaries'].items():
    f=Path(b['binary']);assert hashlib.sha256(f.read_bytes()).hexdigest()==b['binary_sha256'];files['binary/'+name]=f
out=l/'cold_recycling_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local readback-verified cold observer sources, failed builds and qualification; prior pristine sources remain dependencies; not off-device backup');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
