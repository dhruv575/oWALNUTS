import hashlib,json,subprocess,sys
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';model=sys.argv[1];factor=float(sys.argv[2]);root=Path(sys.argv[3])
prior=local/'matched_geometry01'/model if factor==1 else local/'step_ladder01'/(model+'-x4.0')
spec=json.loads((prior/'INPUT.json').read_text());baseline=json.loads((prior/'OUTPUT.json').read_text())
build=json.loads((local/'work_profile_build01/SUMMARY.json').read_text());assert build['passed'];binary=Path(build['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==build['binary_sha256']
inp=root/'INPUT.json';out=root/'OUTPUT.json';inp.write_text(json.dumps(spec)+'\n');subprocess.run([str(binary),str(inp),str(out)],check=True,timeout=150)
current=json.loads(out.read_text());assert current['target_calls']==baseline['target_calls'];works=[]
for a,b in zip(current['chains'],baseline['chains']):
    for key in ['draws','target_calls','retained_divergences','step_size','mass','seed','revision']:assert a[key]==b[key],key
    w=a['work'];assert w['target_calls_total']==w['target_calls_initial']+w['target_calls_forward']+w['target_calls_reverse']
    assert w['all_phase_calls']==a['target_calls'] and w['accepted_forward_micro_steps']<=w['target_calls_forward'];works.append(w)
totals={k:sum(w[k] for w in works) for k in works[0] if k!='refinement_level_built'}
totals['forward_calls_not_in_built_leaves']=totals['target_calls_forward']-totals['accepted_forward_micro_steps']
summary=dict(model=model,factor=factor,exact_parity=True,accounting_verified=True,totals=totals,chains=works,inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),binary,prior/'INPUT.json',prior/'OUTPUT.json',study/'WORK-PROFILE-PROTOCOL.md']})
(root/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(dict(model=model,factor=factor,totals=totals)))
