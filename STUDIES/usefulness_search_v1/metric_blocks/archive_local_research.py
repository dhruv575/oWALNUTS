"""Create and independently read back local evidence without cloud writes."""
import hashlib,io,json,sys,tarfile
from pathlib import Path

study=Path(__file__).resolve().parent;local=study/'local_recovery'
name=sys.argv[1];assert name=='compat01' or name in [f'localscaled{i:02d}' for i in range(1,9)]
root=local/name;summary=json.loads((root/'SUMMARY.json').read_text())
if name!='compat01':assert json.loads((root/'VERIFICATION.json').read_text())['passed']
else:
    assert summary['passed']
    sup=json.loads((root/'SUPERVISION.json').read_text());assert sup['exit_code']==0 and sup['group_drained']
dest=local/(name+'_archive');dest.mkdir(exist_ok=False)
files={str(p.relative_to(root)):p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
for p in (local/'inputs').rglob('*'):
    if p.is_file() and 'models' not in p.relative_to(local/'inputs').parts and '__pycache__' not in p.parts:
        files['restored-inputs/'+str(p.relative_to(local/'inputs'))]=p
for n in ['LOCAL-COMPATIBILITY.md','LOCAL-SCALED-VALIDATION.md','LOCAL-RECOVERY-INPUTS.json','local_compat_worker.py','run_local_compat.py','prepare_local_scaled.py','archive_local_research.py']:
    files['provenance/'+n]=study/n
files['provenance/local-environment.json']=local/'compat01/ENVIRONMENT.json'
runtime=local/'venv/lib/libtbb.so.2';files['runtime/libtbb.so.2']=runtime
manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()}
archive=dest/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    raw=(json.dumps(manifest,indent=2)+'\n').encode();info=tarfile.TarInfo('EVIDENCE-MANIFEST.json');info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
    for n,p in files.items():tar.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as tar:
    restored=json.load(tar.extractfile('EVIDENCE-MANIFEST.json'));assert restored==manifest
    assert set(tar.getnames())==set(manifest)|{'EVIDENCE-MANIFEST.json'}
    for n,e in restored.items():
        raw=tar.extractfile(n).read();assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
receipt=dict(passed=True,archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),members=len(manifest),uncompressed_bytes=sum(e['bytes'] for e in manifest.values()),scope='Local archive read-back/member verification; not an off-device or S3 backup')
(dest/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
