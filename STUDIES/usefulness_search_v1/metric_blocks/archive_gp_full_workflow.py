import hashlib,io,json,tarfile
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_full_workflow01'
s=json.loads((r/'SUMMARY.json').read_text());audit=json.loads((r/'AUDIT.json').read_text());assert s['completed'] and audit['passed'] and len(s['rows'])==28
for name,h in s['inputs'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
for row in s['rows']:
    for name,h in row.get('result',{}).get('inputs',{}).items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
files={str(f.relative_to(p)):f for f in r.rglob('*') if f.is_file() and '__pycache__' not in f.parts}
for name in ['GP-FULL-WORKFLOW-PROTOCOL.md','GP-FULL-WORKFLOW-RESULT.md','prepare_gp_full_workflow.py','gp_full_sampler_worker.py','gp_full_importance_worker.py','time_gp_workflow.py','run_gp_full_workflow.py','analyze_gp_full_workflow.py','archive_gp_full_workflow.py','gp_workflow_setup.py','bounded_transport.py','local_recovery/gp_pilot_replay_archive01/VERIFICATION.json','local_recovery/gp_conditional_local_archive01/VERIFICATION.json','local_recovery/gp24_confirmation_archive01/VERIFICATION.json']:files[name]=p/name
files['reference/REFERENCE.json']=p.parent/'gp_count/REFERENCE.json'
out=l/'gp_full_workflow_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    raw=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        raw=t.extractfile(n).read();assert len(raw)==m['bytes'] and hashlib.sha256(raw).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local full-workflow evidence; compiled target/original pilot dependencies preserved separately; not off-device')
(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
