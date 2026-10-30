import hashlib,io,json,sys,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';name=sys.argv[1]
assert name in ['nativepreflight01','nativepreflight02','nativepreflight03']
root=local/name;summary=json.loads((root/'SUMMARY.json').read_text())
for p in root.glob('*/SUPERVISION.json'):assert json.loads(p.read_text())['group_drained']
files={str(p.relative_to(root)):p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
for p,h in summary['inputs'].items():
    path=Path(p);assert hashlib.sha256(path.read_bytes()).hexdigest()==h
    files['dependencies/'+path.name]=path
for n in ['DOWNLOAD.json','INSTALL-REPORT.json','CONSTRAINTS.txt']:
    files['installation/'+n]=local/'nutpie_baseline'/n
receipt=json.loads((local/'nutpie_baseline/DOWNLOAD.json').read_text(encoding='utf-8-sig'));wheel=local/'nutpie_baseline'/receipt['filename']
assert hashlib.sha256(wheel.read_bytes()).hexdigest()==receipt['sha256'];files['installation/'+wheel.name]=wheel
dest=local/(name+'_archive');dest.mkdir(exist_ok=False);manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()};archive=dest/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    raw=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('EVIDENCE-MANIFEST.json');info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
    for n,p in files.items():tar.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as tar:
    for n,e in manifest.items():
        raw=tar.extractfile(n).read();assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
r=dict(passed=True,study_passed=summary['passed'],members=len(manifest),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local read-back verification; no S3 backup.')
(dest/'VERIFICATION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
