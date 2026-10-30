import hashlib,json,subprocess,sys
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';model=sys.argv[1];factor=float(sys.argv[2]);root=Path(sys.argv[3])
prior=local/'matched_geometry01'/model if factor==1 else local/'step_ladder01'/(model+'-x4.0')
spec=json.loads((prior/'INPUT.json').read_text());baseline=json.loads((prior/'OUTPUT.json').read_text())
build=json.loads((local/'duplicate_audit_build01/SUMMARY.json').read_text());assert build['passed'];binary=Path(build['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==build['binary_sha256']
for enabled in [False,True]:
    label='enabled' if enabled else 'disabled';inp=root/(label+'-INPUT.json');out=root/(label+'-OUTPUT.json');inp.write_text(json.dumps(dict(spec,audit=enabled))+'\n')
    subprocess.run([str(binary),str(inp),str(out)],check=True,timeout=80)
    current=json.loads(out.read_text());assert current['target_calls']==baseline['target_calls']
    for a,b in zip(current['chains'],baseline['chains']):
        for key in ['draws','target_calls','retained_divergences','step_size','mass','seed','revision']:assert a[key]==b[key],key
    if enabled:audits=[c['duplicate_audit'] for c in current['chains']]
totals={key:sum(a[key] for a in audits) for key in ['observed_successful_calls','error_calls','duplicate_successful_calls','output_bit_mismatches','capacity_dropped_calls','nonfinite_calls']}
assert totals['observed_successful_calls']+totals['error_calls']==baseline['target_calls']
summary=dict(model=model,factor=factor,exact_parity=True,totals=totals,calls=baseline['target_calls'],observed_duplicate_fraction=totals['duplicate_successful_calls']/baseline['target_calls'],chains=audits,inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),binary,prior/'INPUT.json',prior/'OUTPUT.json',study/'DUPLICATE-EVALUATION-PROTOCOL.md']})
(root/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(dict(model=model,factor=factor,totals=totals)))
