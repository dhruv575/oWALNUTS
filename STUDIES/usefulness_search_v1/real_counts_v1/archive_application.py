import hashlib,io,json,tarfile
from pathlib import Path
base=Path(__file__).resolve().parent;files={};receipts={}
for folder in ['fresh_remote01','predictive_remote02']:
    root=base/folder;manifest=json.loads((root/'TRANSFER-MANIFEST.json').read_text())
    for n,m in manifest.items():
        f=root/n;assert f.stat().st_size==m['bytes'] and hashlib.sha256(f.read_bytes()).hexdigest()==m['sha256'],(folder,n)
    receipts[folder]=dict(files=len(manifest),bytes=sum(x['bytes'] for x in manifest.values()))
assert json.loads((base/'FRESH-WORKFLOW-AUDIT.json').read_text())['audit_passed'];assert json.loads((base/'PREDICTIVE-SCORE-AUDIT.json').read_text())['passed']
dependency=base.parents[2]/'research-ops/archive/real-counts-training-s3-20261030/VERIFICATION.json';dep=json.loads(dependency.read_text());assert dep['passed'] and dep['sha256']=='da938d25f945fa8affb85753450c7cf6d80a6a831257cc5eab893158d3d69498';files['dependencies/TRAINING-S3-VERIFICATION.json']=dependency
for folder in ['fresh_remote01','predictive_remote02','predictive_bundle01','predictive_target01','predictive_target_check02','predictive_target_supervision01','predictive_check_supervision02']:
    for f in (base/folder).rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts:files['study/'+str(f.relative_to(base))]=f
for f in base.iterdir():
    if f.is_file() and f.suffix in ['.py','.md','.stan','.json']:files['study/'+f.name]=f
out=base/'application_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    assert len(t.getmembers())==len(files)+1
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256'],n
result=dict(passed=True,members=len(files),bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),transfers=receipts,dependency=dep,scope='Verified local fresh workflow/predictive archive including failures; requires exact-version training dependency; not yet uploaded')
(out/'VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
