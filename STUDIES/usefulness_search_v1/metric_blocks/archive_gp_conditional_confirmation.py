import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
import arviz as az
from scipy.special import logsumexp
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_conditional_confirmation01';s=json.loads((r/'SUMMARY.json').read_text());assert s['completed'] and len(s['rows'])==4
assert {x['seed'] for x in s['rows']}==set(range(949200001,949200005))
for name,h in s['inputs'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
ref=json.loads((p.parent/'gp_count/REFERENCE.json').read_text());assert ref['qualified'];ref=ref['stats']
audit=[]
for row in s['rows']:
    d=r/str(row['seed']);supervision=json.loads((d/'SUPERVISION.json').read_text())
    if not (supervision['exit_code']==0 and supervision['group_drained']):
        assert not row['passed'];audit.append(dict(seed=row['seed'],worker_completed=False));continue
    a=np.load(d/'draws.npz');w=a['weight'];v=a['values'];active=w>0
    assert v.shape==(16384,24) and np.isfinite(v[active]).all()
    assert np.allclose(w,np.exp(a['log_weight']-logsumexp(a['log_weight'])),rtol=1e-12,atol=1e-15)
    assert np.allclose(a['log_weight'],a['log_target']-a['log_proposal'],rtol=1e-12,atol=1e-12)
    v=v[active];w=w[active];mean=w@v;sd=np.sqrt(w@((v-mean)**2));mcse=np.sqrt(np.sum((w[:,None]*(v-mean))**2,axis=0))
    for key,value in [('mean',mean),('sd',sd),('mcse',mcse)]:assert np.allclose(row[key],value,rtol=1e-12,atol=1e-12)
    ess=1/np.sum(w*w);assert np.isclose(row['ess'],ess,rtol=1e-12)
    _,pareto_k=az.psislw(a['log_weight']);assert np.isclose(row['pareto_k'],float(pareto_k),rtol=1e-12,atol=1e-12)
    error=abs(mean-ref['mean'])/ref['sd'];sderr=abs(sd/ref['sd']-1);z=abs(mean-ref['mean'])/np.sqrt(mcse**2+np.asarray(ref['mcse'])**2)
    checks=dict(ess=ess>=400,pareto_k=row['pareto_k']<.7,mean_error=max(error)<=.1,sd_error=max(sderr)<=.1,combined_mcse=max(z)<=4)
    assert all(checks.values())==row['passed'] and checks==row['checks']
    audit.append(dict(seed=row['seed'],worker_completed=True,checks={k:bool(v) for k,v in checks.items()}))
assert s['all_qualified']==all(x['passed'] for x in s['rows'])
(r/'AUDIT.json').write_text(json.dumps(dict(passed=True,rows=audit),indent=2)+'\n')
lines=['# Fresh conditional-importance confirmation','','Four fresh replicates,16384 proposals each; all24 quantities and prospectively matched accuracy tolerances.','','| Seed | Qualified | Importance ESS | Pareto k | Max mean error | Max SD error | Max combined z |','|---|---|---|---|---|---|---|']
for row in s['rows']:
    if 'ess' in row:lines.append(f"| {row['seed']} | {row['passed']} | {row['ess']:.3f} | {row['pareto_k']:.4f} | {max(row['mean_error_sd']):.5f} | {max(row['relative_sd_error']):.5f} | {max(row['combined_z']):.4f} |")
    else:lines.append(f"| {row['seed']} | worker failed | | | | | |")
lines+=['','No speed ranking follows: setup costs and precision must be matched, and importance ESS is not interchangeable with chain ESS. Preparation, factor extraction and conditional optimization costs must be included. No demonstrated WALNUTS application value, uniqueness or novelty.']
(p/'GP-CONDITIONAL-CONFIRMATION-RESULT.md').write_text('\n'.join(lines)+'\n')
files={str(f.relative_to(p)):f for f in r.rglob('*') if f.is_file()}
for name in ['GP-CONDITIONAL-CONFIRMATION-PROTOCOL.md','GP-CONDITIONAL-CONFIRMATION-RESULT.md','prepare_gp_conditional_confirmation.py','gp_conditional_confirmation_worker.py','run_gp_conditional_confirmation.py','archive_gp_conditional_confirmation.py','local_recovery/gp_conditional_local_archive01/VERIFICATION.json']:files[name]=p/name
files['reference/REFERENCE.json']=p.parent/'gp_count/REFERENCE.json'
out=l/'gp_conditional_confirmation_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    raw=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        raw=t.extractfile(n).read();assert len(raw)==m['bytes'] and hashlib.sha256(raw).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local evidence; depends on preserved approximation preflight/target archive; not off-device')
(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
