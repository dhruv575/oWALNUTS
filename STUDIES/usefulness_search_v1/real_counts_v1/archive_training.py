import hashlib,io,json,tarfile
from pathlib import Path
base=Path(__file__).resolve().parent;local=base.parent/'metric_blocks/local_recovery';files={}
for n in ['REFERENCE-AUDIT.json','IMPORTANCE-AUDIT.json','SAMPLER-SCREEN-AUDIT.json']:
    assert json.loads((base/n).read_text())['audit_passed']
for folder in ['reference_remote01','importance_remote01','sampler_screen_remote01','proposal_preflight01','proposal_preflight_supervision01','source','data01','exact_controls01']:
    for f in (base/folder).rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts:files['study/'+str(f.relative_to(base))]=f
for f in base.iterdir():
    if f.is_file() and f.suffix in ['.py','.md','.json']:files['study/'+f.name]=f
for folder in ['gp_aws_runtime_bundle01','gp_aws_runtime_preflight01']:
    for f in (local/folder).rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts:files['runtime/'+folder+'/'+str(f.relative_to(local/folder))]=f
# Include the exact supervisor dependency used by references.
f=local/'gp_aws_full_remote01/resource_monitor.py';files['runtime/resource_monitor.py']=f
out=base/'training_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    assert len(t.getmembers())==len(files)+1
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
result=dict(passed=True,members=len(files),bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local verified archive of real training studies and runtime dependencies; contains failures; not yet S3')
(out/'VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
