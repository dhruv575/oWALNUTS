import hashlib,io,json,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'step_ladder01'
s=json.loads((root/'SUMMARY.json').read_text());assert s['unchanged'] and len(s['rows'])==20
for p,h in s['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
for r in s['rows']:assert json.loads((root/r['folder']/'SUPERVISION.json').read_text())['group_drained']
files={str(p.relative_to(local)):p for p in root.rglob('*') if p.is_file()}
for name in ['run_step_ladder.py','analyze_step_ladder.py','archive_step_ladder.py','STEP-LADDER-PROTOCOL.md','STEP-LADDER-REPORT.md','STEP-LADDER-ANALYSIS.json','STEP-LADDER-AUDIT.md','matched_geometry_worker.py']:
    files['source/'+name]=study/name
dest=local/'step_ladder_archive01';dest.mkdir(exist_ok=False);archive=dest/'evidence.tar.gz'
manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()}
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,p in files.items():t.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,r in manifest.items():
        data=t.extractfile(n).read();assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
out=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local complete ladder evidence read-back, not statistical success or off-device backup.')
(dest/'VERIFICATION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
