import hashlib,io,json,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'duplicate_audit01';s=json.loads((root/'SUMMARY.json').read_text());assert s['unchanged'] and len(s['rows'])==10
rows=[]
for row in s['rows']:
    assert row['completed'];folder=root/row['folder'];r=json.loads((folder/'SUMMARY.json').read_text());assert r['exact_parity']
    for p,h in r['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
    assert r['observed_duplicate_fraction']==r['totals']['duplicate_successful_calls']/r['calls'];rows.append(r)
eligible=all(r['totals']['output_bit_mismatches']==0 for r in rows) and sum(r['factor']==1 and r['observed_duplicate_fraction']>=.2 for r in rows)>=2
out=dict(eligible_for_cache_experiment=eligible,rows=rows,scope='Exact-coordinate observation only; bounded coverage, no runtime gain.')
(study/'DUPLICATE-EVALUATION-ANALYSIS.json').write_text(json.dumps(out,indent=2)+'\n')
lines=['# Exact duplicate evaluation audit','', 'All10 enabled/disabled cases preserve prior draws, target calls and diagnostics exactly. Two instrument unit tests pass. Zero exact duplicates or repeated-output mismatches were observed.','', '| Target | Step factor | Calls | Duplicates | Capacity-dropped calls |','|---|---|---|---|---|']
for r in rows:lines.append(f"| {r['model']} | {r['factor']} | {r['calls']} | {r['totals']['duplicate_successful_calls']} | {r['totals']['capacity_dropped_calls']} |")
lines+=['','Cache experiment justified by frozen rule: '+str(eligible)+'.','At factor1, four targets have complete finite-call coverage. Centered eight schools and all factor4 cases overflow storage; zero observed duplicates does not bound duplication among unrecorded keys. No cache implementation is justified by this screen. No runtime improvement is claimed.','', 'Next inspect existing per-phase forward/refinement/reverse work counters with unchanged trajectories before choosing another mechanism. Initial-evaluation reuse already exists; do not rediscover it as a new optimization.']
(study/'DUPLICATE-EVALUATION-REPORT.md').write_text('\n'.join(lines)+'\n')
files={}
for directory in [root,local/'duplicate_audit_build01',study/'duplicate_eval_runner']:
    for p in directory.rglob('*'):
        if p.is_file():files[str(p.relative_to(study))]=p
for name in ['duplicate_audit_fragment.rs','prepare_duplicate_audit.py','build_duplicate_audit.py','duplicate_audit_worker.py','run_duplicate_audit.py','finalize_duplicate_audit.py','DUPLICATE-EVALUATION-PROTOCOL.md','DUPLICATE-EVALUATION-ANALYSIS.json','DUPLICATE-EVALUATION-REPORT.md','local_recovery/DUPLICATE-AUDIT-PROVENANCE.json']:files[name]=study/name
build=json.loads((local/'duplicate_audit_build01/SUMMARY.json').read_text());files['binary/runner']=Path(build['binary'])
dest=local/'duplicate_audit_archive01';dest.mkdir(exist_ok=False);archive=dest/'evidence.tar.gz';manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()}
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,p in files.items():t.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,r in manifest.items():
        data=t.extractfile(n).read();assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local raw/source/binary archive read-back, not off-device backup.')
(dest/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(dict(eligible=eligible,archive=receipt)))
