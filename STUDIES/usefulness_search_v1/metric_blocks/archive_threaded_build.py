import hashlib,io,json,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'threaded_build01'
s=json.loads((root/'SUMMARY.json').read_text());sup=json.loads((root/'SUPERVISION.json').read_text());assert s['passed'] and sup['exit_code']==0 and sup['group_drained']
files={p.name:p for p in root.iterdir() if p.is_file()}
for i,(name,h) in enumerate(s['inputs'].items()):
    p=Path(name);assert hashlib.sha256(p.read_bytes()).hexdigest()==h;files[f'dependencies/{i}-{p.name}']=p
for p in [study/'run_threaded_native_build.py',Path(__file__),local/'inputs/resource_monitor.py']:files['provenance/'+p.name]=p
dest=local/'threaded_build01_archive';dest.mkdir(exist_ok=False);manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()};archive=dest/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    raw=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('EVIDENCE-MANIFEST.json');info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
    for n,p in files.items():tar.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as tar:
    for n,e in manifest.items():
        raw=tar.extractfile(n).read();assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
r=dict(passed=True,members=len(manifest),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),density_error=s['density_error'],gradient_error=s['gradient_error'],scope='Local archive read-back; no S3/off-device backup.')
(dest/'VERIFICATION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
