import hashlib,io,json,tarfile,difflib
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';root=l/'banana_recycling_test01';s=json.loads((root/'SUMMARY.json').read_text());assert s['passed']
for f,h in s['inputs'].items():assert hashlib.sha256(Path(f).read_bytes()).hexdigest()==h
truth=np.array(json.loads((root/'EXACT-CONTROL.json').read_text())['truth']);tol=np.array(json.loads((root/'EXACT-CONTROL.json').read_text())['tolerances'])
for row in s['rows']:
    prefix=row['representation']+'-'+row['engine'];wal=row['engine']=='wal';arms=[json.loads((root/(prefix+'-'+a)/'RAW.json').read_text()) for a in ['original','disabled','enabled']];full=json.loads((root/(prefix+'-full')/'RAW.json').read_text());conditional=[];ordinary=[]
    for a,b,c,f in zip(*(r['chains'] for r in arms),full['chains']):
        for k in ['draw_sha256','target_calls','retained_divergences']+(['work'] if wal else ['warmup_calls','total_steps']):assert a[k]==b[k]==c[k]
        q=np.array(f['draws' if wal else 'all_draws'],dtype='<f8');assert hashlib.sha256(q.tobytes()).hexdigest()==c['draw_sha256'];q=q[0 if wal else 1000:];v=np.array(f['recycled'])[0 if wal else 1000:]
        if row['representation']=='latent':q[:,1::2]+=5*(q[:,::2]**2-1)
        obs=np.concatenate([q,q*q,(q<0).astype(float),(q< -2).astype(float)],axis=1);sm=c['summary' if wal else 'conditional_summary'];om=a['summary' if wal else 'ordinary_summary'];np.testing.assert_allclose(sm['mean'],v.mean(0),rtol=2e-13,atol=1e-10);np.testing.assert_allclose(om['mean'],obs.mean(0),rtol=2e-13,atol=1e-10);conditional.append(v.mean(0));ordinary.append(obs.mean(0))
    if row['representation']=='latent':assert np.all(abs(np.mean(conditional,0)-truth)<=tol) and np.all(abs(np.mean(ordinary,0)-truth)<=tol)
patches=[]
for old,new,allowed in [('recycling_source03','banana_wal_source01','src/recycling.rs'),('native_recycling_source01','banana_native_source01','src/research_recycling.rs')]:
    for f in (l/old).rglob('*'):
        if not f.is_file():continue
        rel=f.relative_to(l/old);g=l/new/rel
        if str(rel)!=allowed:assert f.read_bytes()==g.read_bytes(),str(rel)
    patches.extend(difflib.unified_diff((l/old/allowed).read_text().splitlines(True),(l/new/allowed).read_text().splitlines(True),fromfile=old+'/'+allowed,tofile=new+'/'+allowed,n=0))
(p/'BANANA-RECYCLING-OBSERVER.patch').write_text(''.join(patches))
(p/'BANANA-RECYCLING-REPLAY.json').write_text(json.dumps(dict(passed=True,scope='Independent draw-hash/work parity, original-coordinate summary and truth replay; source changes restricted to observer modules'),indent=2)+'\n')
files={}
for name in ['banana_wal_source01','banana_native_source01','banana_recycling_build01','banana_recycling_test01']:
    for f in (l/name).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for name in s['binaries']:
    for f in (p/name).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for pattern in ['*banana_recycling.py','archive_banana_qualification.py','banana_core.rs','BANANA-RECYCLING-*']:
    for f in p.glob(pattern):
        if f.is_file():files[f.name]=f
for name in ['native_recycling_archive01','compact_validation_archive01','recycled_baseline_screen_archive01']:
    f=l/name/'VERIFICATION.json';files[str(f.relative_to(p))]=f
for name,b in s['binaries'].items():
    f=Path(b['binary']);assert hashlib.sha256(f.read_bytes()).hexdigest()==b['binary_sha256'];files['binary/'+name]=f
out=l/'banana_recycling_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local verified source and qualification archive; prior pristine sources remain dependencies; not off-device backup');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
