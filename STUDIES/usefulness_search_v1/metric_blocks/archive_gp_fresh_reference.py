import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np,arviz as az
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_fresh_reference01';s=json.loads((r/'SUMMARY.json').read_text());assert s['completed'] and len(s['rows'])==8
assert {(x['scenario'],x['rep']) for x in s['rows']}=={(a,b) for a in range(4) for b in range(2)}
for name,h in s['inputs'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
def stats(v):
    ds=az.convert_to_dataset({'p':v});result={k:np.asarray(fn(ds).p) for k,fn in [('rhat',lambda d:az.rhat(d,method='rank')),('bulk',lambda d:az.ess(d,method='bulk')),('tail',lambda d:az.ess(d,method='tail')),('mcse',lambda d:az.mcse(d,method='mean'))]};result.update(mean=v.mean((0,1)),sd=v.reshape(-1,24).std(0,ddof=1));return result
for row in s['rows']:
    for name,h in row.get('inputs',{}).items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
    if 'stats' not in row:assert not row['passed'];continue
    d=r/f"{row['scenario']}-{row['rep']}";v=np.load(d/'FUNCTIONALS.npz')['values'];assert v.shape==(4,8000,24);actual=stats(v)
    for k,a in actual.items():assert np.allclose(row['stats'][k],a,rtol=1e-12,atol=1e-12)
    div=int(np.load(d/'DRAWS-STATS.npz')['sample_stats__diverging'].sum());assert row['divergences']==div
    qualified=all(np.isfinite(a).all() for a in actual.values()) and div==0 and max(actual['rhat'])<=1.01 and min(actual['bulk'])>=1000 and min(actual['tail'])>=1000
    assert bool(qualified)==row['passed']
for reference in s['references']:
    scenario=reference['scenario'];pair=sorted([x for x in s['rows'] if x['scenario']==scenario],key=lambda x:x['rep'])
    if not all(x['passed'] for x in pair):assert not reference['passed'];continue
    v=np.concatenate([np.load(r/f'{scenario}-{rep}/FUNCTIONALS.npz')['values'] for rep in range(2)]);actual=stats(v)
    for k,a in actual.items():assert np.allclose(reference['stats'][k],a,rtol=1e-12,atol=1e-12)
    a,b=[x['stats'] for x in pair];delta=abs(np.asarray(a['mean'])-b['mean']);z=delta/np.sqrt(np.asarray(a['mcse'])**2+np.asarray(b['mcse'])**2);sd_difference=abs(np.asarray(a['sd'])-b['sd'])/((np.asarray(a['sd'])+b['sd'])/2)
    checks=dict(finite=all(np.isfinite(x).all() for x in actual.values()),rhat=max(actual['rhat'])<=1.01,bulk=min(actual['bulk'])>=4000,tail=min(actual['tail'])>=2000,relative_mcse=max(actual['mcse']/actual['sd'])<=.02,group_z=max(z)<=4,group_mean=max(delta/actual['sd'])<=.05,group_sd=max(sd_difference)<=.1)
    assert checks==reference['checks'] and all(checks.values())==reference['passed']
(r/'AUDIT.json').write_text(json.dumps(dict(passed=True,groups=8,reference_qualified=[x['scenario'] for x in s['references'] if x['passed']]),indent=2)+'\n')
lines=['# Fresh-data independent reference candidates','','Two separately seeded four-chain groups per frozen dataset. All24 quantities checked; generative truth was not used.','','| Scenario | Qualified groups | Combined reference qualified |','|---|---|---|']
for ref in s['references']:lines.append(f"| {ref['scenario']} | {sum(x['passed'] for x in s['rows'] if x['scenario']==ref['scenario'])}/2 | {ref['passed']} |")
lines+=['','These are practical checked-functional references, not proof of complete posterior exploration. Any failed case remains in the study and cannot be silently discarded. No algorithm advantage or real-world application follows from reference preparation.']
(p/'GP-FRESH-REFERENCE-RESULT.md').write_text('\n'.join(lines)+'\n')
files={str(f.relative_to(p)):f for folder in [r,l/'gp_fresh_data01'] for f in folder.rglob('*') if f.is_file()}
for name in ['GP-FRESH-DATA-PROTOCOL.md','prepare_gp_fresh_data.py','GP-FRESH-REFERENCE-PROTOCOL.md','GP-FRESH-REFERENCE-RESULT.md','gp_fresh_reference_worker.py','run_gp_fresh_reference.py','archive_gp_fresh_reference.py','native_common.py']:files[name]=p/name
out=l/'gp_fresh_reference_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    raw=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        raw=t.extractfile(n).read();assert len(raw)==m['bytes'] and hashlib.sha256(raw).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local new-data/reference evidence; compiled target dependencies retained separately; not off-device')
(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
