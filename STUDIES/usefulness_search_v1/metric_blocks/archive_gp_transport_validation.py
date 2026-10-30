import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_transport_validation01';s=json.loads((r/'SUMMARY.json').read_text());assert s['completed'] and len(s['rows'])==48;files={}
for n,h in s['source_hashes'].items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h
failures=[]
for row in s['rows']:
    for name,h in row.get('inputs',{}).items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
    if 'functionals' in row:
        f=row['functionals'];assert min(f['bulk'])==row['bulk'] and min(f['tail'])==row['tail'] and max(f['rhat'])==row['rhat']
        gates=dict(rhat=row['rhat']<=1.01,bulk=row['bulk']>=400,tail=row['tail']>=400,divergences=row['divergences']==0,mean_z=row['max_z']<=4.5,mean_sd=row['max_mean_sd']<=.1,sd_error=row['max_sd_error']<=.1);assert all(gates.values())==row['passed']
    else:gates=dict(worker_completed=False)
    if not row['passed']:failures.append(dict(fold=row['fold'],seed=row['seed'],transform=row['transform'],mode=row['mode'],failed_gates=[k for k,v in gates.items() if not v]))
assert s['all_qualified']==(not failures)
if failures:assert s['contrasts']==[] and not s['primary_passed']
(r/'QUALIFICATION-AUDIT.json').write_text(json.dumps(dict(passed=True,failures=failures),indent=2)+'\n')
lines=['# Fresh fixed-map workflow validation','','Eight fresh seed sets across four fixed maps, six workflows,48 fits. Original qualification thresholds and the all-fit gate were retained.','','| Workflow | Qualified fits | Retained divergences | Minimum bulk ESS | Minimum tail ESS |','|---|---|---|---|---|']
for transform,mode in [('raw','walnuts_dense'),('raw','low_rank'),('affine','walnuts_dense'),('affine','diag'),('quadratic','walnuts_diag'),('quadratic','diag')]:
    rows=[x for x in s['rows'] if x['transform']==transform and x['mode']==mode];assert len(rows)==8;lines.append(f"| {transform}/{mode} | {sum(x['passed'] for x in rows)}/8 | {sum(x.get('divergences',0) for x in rows)} | {min(x.get('bulk',0) for x in rows):.3f} | {min(x.get('tail',0) for x in rows):.3f} |")
lines+=['',f"Primary gate passed: {s['primary_passed']}.",'','Failures: '+json.dumps(failures), '','Contrasts: '+json.dumps(s['contrasts']), '','If any fit fails, all competitive efficiency ratios are withheld as frozen; no failed seed, workflow or functional is removed. These are fresh sampler seeds conditional on fixed exposed maps, not new data or map-training validation. Pilot/fitting costs remain necessary, and concurrent elapsed clocks are not timing evidence. The successful conditional-importance method is not superseded by this study.','','A failed fixed-budget control does not establish intrinsic candidate superiority. Diagnose whether remaining failures reflect insufficient precision, numerical divergence or reference disagreement before designing any new experiment. Do not append draws to this validation or relax its thresholds. Any larger-budget confirmation needs a new frozen budget and fresh seeds; retain this outcome. No production change or goal completion.']
(p/'GP-TRANSPORT-VALIDATION-RESULT.md').write_text('\n'.join(lines)+'\n')
for f in r.rglob('*'):
    if f.is_file():files[str(f.relative_to(p))]=f
for name in ['GP-TRANSPORT-VALIDATION-PROTOCOL.md','GP-TRANSPORT-VALIDATION-RESULT.md','prepare_gp_transport_validation.py','gp_transport_validation_worker.py','run_gp_transport_validation.py','archive_gp_transport_validation.py','local_recovery/gp_transport_native_repair_archive01/VERIFICATION.json','local_recovery/gp_transport_calibration01/COST-LEDGER.json','local_recovery/localscaled01/REFERENCES.json']:files[name]=p/name
out=l/'gp_transport_validation_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive, depends on preserved calibration/target archives; not off-device');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
