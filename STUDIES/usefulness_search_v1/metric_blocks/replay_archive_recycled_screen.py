import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
from scipy.special import ndtr
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'recycled_baseline_screen01';s=json.loads((r/'SUMMARY.json').read_text());a=json.loads((p/'RECYCLED-BASELINE-SCREEN-ANALYSIS.json').read_text());assert s['passed']
for f,h in s['inputs'].items():assert hashlib.sha256(Path(f).read_bytes()).hexdigest()==h
for result in a['results']:
    target=result['target'];d=10 if target=='noncentered' else 2;var=np.array([9.]+[1.]*9 if d==10 else [2.,2.]);truth=np.r_[np.zeros(d),var,np.full(d,.5),ndtr(-2/np.sqrt(var))];scale=np.r_[np.sqrt(var),var,np.ones(2*d)];means={arm:[] for arm in s['builds']};costs={arm:[] for arm in s['builds']}
    for b in range(16):
        f=r/f'{target}-{b:02d}';times=json.loads((f/'TIMINGS.json').read_text());assert len(times)==18
        for arm in means:
            data=json.loads((f/f'RAW-{arm}.json').read_text())
            for c in data['chains']:
                sm=c['summary'] if arm.startswith('wal') else c['conditional_summary' if arm.endswith('recycled') else 'ordinary_summary'];means[arm].append(sm['mean'])
            for c in data['chains']:c.pop('seconds')
            digest=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            ts=[t for t in times if t['arm']==arm];assert len(ts)==3 and all(t['canonical_sha256']==digest for t in ts);costs[arm].append(sum(t['seconds'] for t in ts)/3)
    for j,family in enumerate(result['families']):
        sl=slice(j*d,(j+1)*d);mse={arm:float(np.square((np.array(v)[:,sl]-truth[sl])/scale[sl]).mean()) for arm,v in means.items()}
        for arm in mse:assert np.isclose(mse[arm],family['mse'][arm],rtol=1e-13,atol=1e-16)
        for c in family['comparisons']:
            mr=mse[c['control']]/mse['wal_recycled'];cr=np.mean(costs[c['control']])/np.mean(costs['wal_recycled']);assert np.isclose(c['mse_ratio'],mr) and np.isclose(c['cost_ratio'],cr) and np.isclose(c['cost_adjusted_ratio'],mr*cr)
checks={c['control']:c['descriptive_endpoint_range'][0]>1.2 for c in a['results'][0]['families'][1]['comparisons'] if not c['control'].startswith('wal')};assert checks==a['primary_controls'];assert a['primary_passed']==(all(checks.values()) and a['primary_z_gate'])
(p/'RECYCLED-BASELINE-SCREEN-REPLAY.json').write_text(json.dumps(dict(passed=True,scope='Independent canonical timing-output, MSE/cost point estimates and gate replay; bootstrap endpoint generation is in frozen analysis, not independently reimplemented'),indent=2)+'\n')
files={}
for name in ['native_compact_build01','native_compact_test01','compact_wal_stable_build01','compact_wal_stable_test01','recycled_baseline_screen01']:
    for f in (l/name).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for name in ['native_compact_pristine_runner','native_compact_recycling_runner']:
    for f in (p/name).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for pattern in ['*native_compact*.*','*compact_wal_stable.py','*recycled_baseline_screen.py','replay_archive_recycled_screen.py','NATIVE-COMPACT-*','RECYCLED-BASELINE-SCREEN-*']:
    for f in p.glob(pattern):
        if f.is_file():files[f.name]=f
for name in ['native_recycling_archive01','compact_validation_archive01']:
    f=l/name/'VERIFICATION.json';files[str(f.relative_to(p))]=f
for arm,b in s['builds'].items():
    f=Path(b['binary']);assert hashlib.sha256(f.read_bytes()).hexdigest()==b['binary_sha256'];files['binary/'+arm]=f
out=l/'recycled_baseline_screen_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local readback-verified evidence; prior source archives remain dependencies; not off-device backup');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
