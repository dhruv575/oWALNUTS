import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'bounded_gp_validation01';s=json.loads((r/'SUMMARY.json').read_text());assert s['completed'] and len(s['rows'])==48;files={}
configs=[('raw','walnuts_dense'),('raw','low_rank'),('affine','walnuts_dense'),('affine','diag'),('bounded','walnuts_dense'),('bounded','low_rank')]
expected={(fold,948700001+2*fold+rep,t,m) for fold in range(4) for rep in range(2) for t,m in configs}
assert {(x['fold'],x['seed'],x['transform'],x['mode']) for x in s['rows']}==expected
for n,h in s['source_hashes'].items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h
ref=json.loads((l/'localscaled01/REFERENCES.json').read_text())['gp_pois_regr-gp_pois_regr'];assert ref['passed']
failures=[]
for row in s['rows']:
    for name,h in row.get('inputs',{}).items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
    if 'functionals' in row:
        f=row['functionals'];assert min(f['bulk'])==row['bulk'] and min(f['tail'])==row['tail'] and max(f['rhat'])==row['rhat']
        assert all(np.isfinite(v).all() for v in f.values())
        mean=np.asarray(f['mean']);sd=np.asarray(f['sd']);mcse=np.asarray(f['mcse'])
        checks={'max_z':max(abs(mean-ref['mean'])/np.sqrt(mcse**2+np.asarray(ref['mcse'])**2)), 'max_mean_sd':max(abs(mean-ref['mean'])/ref['sd']), 'max_sd_error':max(abs(sd/ref['sd']-1))}
        for key,value in checks.items():assert np.isclose(row[key],value,rtol=1e-12,atol=1e-12)
        gates=dict(rhat=row['rhat']<=1.01,bulk=row['bulk']>=400,tail=row['tail']>=400,divergences=row['divergences']==0,mean_z=row['max_z']<=4.5,mean_sd=row['max_mean_sd']<=.1,sd_error=row['max_sd_error']<=.1);assert all(gates.values())==row['passed']
    else:gates=dict(worker_completed=False)
    if not row['passed']:failures.append(dict(fold=row['fold'],seed=row['seed'],transform=row['transform'],mode=row['mode'],failed_gates=[k for k,v in gates.items() if not v]))
assert s['all_qualified']==(not failures)
if failures:assert s['contrasts']==[] and not s['primary_passed']
else:
    ledger=json.loads((l/'gp_transport_calibration01/COST-LEDGER.json').read_text())
    pilot={x['fold']:x['pilot_gradient_calls'] for x in ledger['pilots']}
    for item in ledger['pilots']:
        receipt=Path(item['receipt']);assert hashlib.sha256(receipt.read_bytes()).hexdigest()==item['sha256']
    assert len(s['contrasts'])==10
    index={(x['fold'],x['seed'],x['transform'],x['mode']):x for x in s['rows']}
    resamples=np.random.default_rng(948800001).integers(0,4,(10000,4))
    for c in s['contrasts']:
        transform,mode=c['comparator'].split('-');logs=[]
        for fold in range(4):
            paired=[]
            for rep in range(2):
                seed=948700001+2*fold+rep
                a=index[fold,seed,'bounded','walnuts_dense'];b=index[fold,seed,transform,mode]
                ac=a['calls']['gradient']+(pilot[fold] if c['pilot_inclusive'] else 0)
                bc=b['calls']['gradient']+(pilot[fold] if c['pilot_inclusive'] and transform!='raw' else 0)
                paired.append(np.log(a['bulk']*bc/(b['bulk']*ac)))
            logs.append(np.mean(paired))
        logs=np.asarray(logs);interval=np.quantile(np.exp(logs[resamples].mean(1)),[.025,.975])
        assert np.isclose(c['ratio'],np.exp(logs.mean()),rtol=1e-12)
        assert np.allclose(c['interval'],interval,rtol=1e-12)
    assert s['primary_passed']==all(c['interval'][0]>1.2 for c in s['contrasts'] if c['pilot_inclusive'])
(r/'QUALIFICATION-AUDIT.json').write_text(json.dumps(dict(passed=True,failures=failures),indent=2)+'\n')
lines=['# Fresh fixed-map workflow validation','','Eight fresh seed sets across four fixed maps, six workflows,48 fits. Original qualification thresholds and the all-fit gate were retained.','','| Workflow | Qualified fits | Retained divergences | Minimum bulk ESS | Minimum tail ESS |','|---|---|---|---|---|']
for transform,mode in [('raw','walnuts_dense'),('raw','low_rank'),('affine','walnuts_dense'),('affine','diag'),('bounded','walnuts_dense'),('bounded','low_rank')]:
    rows=[x for x in s['rows'] if x['transform']==transform and x['mode']==mode];assert len(rows)==8;lines.append(f"| {transform}/{mode} | {sum(x['passed'] for x in rows)}/8 | {sum(x.get('divergences',0) for x in rows)} | {min(x.get('bulk',0) for x in rows):.3f} | {min(x.get('tail',0) for x in rows):.3f} |")
lines+=['',f"Primary gate passed: {s['primary_passed']}.",'','Failures: '+json.dumps(failures), '','Contrasts: '+json.dumps(s['contrasts']), '','If any fit fails, all competitive efficiency ratios are withheld as frozen; no failed seed, workflow or functional is removed. These are fresh sampler seeds conditional on fixed exposed maps, not new data or map-training validation. Pilot/fitting costs remain necessary, and concurrent elapsed clocks are not timing evidence. The successful conditional-importance method is not superseded by this study.','','A failed fixed-budget control does not establish intrinsic candidate superiority. Diagnose whether remaining failures reflect insufficient precision, numerical divergence or reference disagreement before designing any new experiment. Do not append draws to this validation or relax its thresholds. Any larger-budget confirmation needs a new frozen budget and fresh seeds; retain this outcome. No production change or goal completion.']
(p/'BOUNDED-GP-VALIDATION-RESULT.md').write_text('\n'.join(lines)+'\n')
for f in r.rglob('*'):
    if f.is_file():files[str(f.relative_to(p))]=f
for name in ['BOUNDED-GP-VALIDATION-PROTOCOL.md','BOUNDED-GP-VALIDATION-RESULT.md','prepare_bounded_gp_validation.py','bounded_gp_validation_worker.py','run_bounded_gp_validation.py','archive_bounded_gp_validation.py','local_recovery/bounded_gp_calibration_archive01/VERIFICATION.json','local_recovery/gp_transport_calibration01/COST-LEDGER.json','local_recovery/localscaled01/REFERENCES.json']:files[name]=p/name
out=l/'bounded_gp_validation_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive, depends on preserved calibration/target archives; not off-device');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
