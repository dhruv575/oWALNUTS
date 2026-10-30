import hashlib,io,json,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'work_profile01';s=json.loads((root/'SUMMARY.json').read_text());assert s['unchanged'] and len(s['rows'])==10
rows=[]
for entry in s['rows']:
    assert entry['completed'];r=json.loads((root/entry['folder']/'SUMMARY.json').read_text());assert r['exact_parity'] and r['accounting_verified']
    for p,h in r['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
    t=r['totals'];assert t['target_calls_total']==t['target_calls_initial']+t['target_calls_forward']+t['target_calls_reverse']
    ideal=t['accepted_forward_micro_steps']+t['target_calls_initial'];ratio=None
    if entry['factor']==1:
        comparison=json.loads((local/'matched_geometry01'/entry['model']/'SUMMARY.json').read_text())
        if comparison['qualified_ratios'] is not None:ratio=comparison['qualified_ratios']['efficiency']*t['all_phase_calls']/ideal
    rows.append(dict(model=entry['model'],factor=entry['factor'],totals=t,reverse_fraction=t['target_calls_reverse']/t['all_phase_calls'],unbuilt_forward_fraction=t['forward_calls_not_in_built_leaves']/t['all_phase_calls'],fixed_draw_accounting_only_native_ratio=ratio,chains=r['chains']))
out=dict(rows=rows,scope='Exposed work accounting, not an optimization or runtime comparison.')
(study/'WORK-PROFILE-ANALYSIS.json').write_text(json.dumps(out,indent=2)+'\n')
lines=['# Kernel work profile','', 'All10 replays preserve retained draws and target calls exactly. Actual calls reconcile with telemetry.','', '| Target | Factor | Calls | Reverse fraction | Forward not in built leaves | Fixed-draw accounting-only native ratio |','|---|---|---|---|---|---|']
for r in rows:
    ratio=r['fixed_draw_accounting_only_native_ratio'];lines.append(f"| {r['model']} | {r['factor']} | {r['totals']['all_phase_calls']} | {r['reverse_fraction']:.3%} | {r['unbuilt_forward_fraction']:.3%} | "+(f'{ratio:.3f}' if ratio is not None else 'unqualified/not evaluated')+' |')
lines+=['','The last column is arithmetic only: hold the observed draws fixed and remove all reverse calls and forward calls not attached to built leaves. It is not an attainable speedup, not a bound on a different algorithm, and not permission to remove correctness checks. On the three qualified factor1 targets it still falls below native NUTS. Improving those results requires changing mixing behavior as well as, or instead of, this accounting overhead.','', 'Factor4 spends roughly60% of calls outside built-leaf forward work, consistent with its failed efficiency ladder. Existing studies uturn_default_v1 and reverse_coarser_policy_v1/v2 already reject broad promotion of their alternatives; do not simply repeat those changes.','', 'Next diagnostic: determine how much of the remaining gap persists when the research runner uses a single refinement level with a permissive local energy threshold, under the same geometry and native step size. This is an algorithmic ablation, not a proposed default or evidence of useful improvement. Preserve ordinary NUTS differences in turning, selection and divergence handling. No result is available yet.']
(study/'WORK-PROFILE-REPORT.md').write_text('\n'.join(lines)+'\n')
files={}
for directory in [root,local/'work_profile_build01',study/'work_profile_runner']:
    for p in directory.rglob('*'):
        if p.is_file():files[str(p.relative_to(study))]=p
for name in ['prepare_work_profile.py','build_work_profile.py','work_profile_worker.py','run_work_profile.py','finalize_work_profile.py','WORK-PROFILE-PROTOCOL.md','WORK-PROFILE-ANALYSIS.json','WORK-PROFILE-REPORT.md','local_recovery/WORK-PROFILE-PROVENANCE.json']:files[name]=study/name
build=json.loads((local/'work_profile_build01/SUMMARY.json').read_text());files['binary/runner']=Path(build['binary'])
dest=local/'work_profile_archive01';dest.mkdir(exist_ok=False);archive=dest/'evidence.tar.gz';manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()}
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,p in files.items():t.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,r in manifest.items():
        data=t.extractfile(n).read();assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local evidence/source/binary read-back, not off-device backup.')
(dest/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
