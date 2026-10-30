import hashlib,io,json,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'counter01'
s=json.loads((root/'SUMMARY.json').read_text());sup=json.loads((root/'SUPERVISION.json').read_text());assert s['passed'] and sup['exit_code']==0 and sup['group_drained']
files={str(p.relative_to(root)):p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
for i,(name,h) in enumerate(s['inputs'].items()):
    p=Path(name);assert hashlib.sha256(p.read_bytes()).hexdigest()==h;files[f'dependencies/{i}-{p.name}']=p
for arm in ['draw_diag','diag','low_rank']:
    prior=local/'nativepreflight03'/arm/'RESULT.json';current=root/arm/'RESULT.json';a=json.loads(prior.read_text());b=json.loads(current.read_text());assert a['draws']==b['draws'] and a['retained_divergences']==b['retained_divergences'];files[f'parent/{arm}-RESULT.json']=prior
for p in [local/'nativepreflight03_archive/VERIFICATION.json',local/'threaded_build01/SUMMARY.json',local/'threaded_build01/sblrc-blr.data.json',local/'threaded_build01/sblrc-blr.stan',study/'run_counted_native.py',Path(__file__)]:files['provenance/'+p.name]=p
dest=local/'counter01_archive';dest.mkdir(exist_ok=False);manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()};archive=dest/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    raw=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('EVIDENCE-MANIFEST.json');info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
    for n,p in files.items():tar.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as tar:
    for n,e in manifest.items():
        raw=tar.extractfile(n).read();assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
r=dict(passed=True,members=len(manifest),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),all_three_retained_trajectories_identical=True,scope='Local archive read-back verification; no off-device/S3 backup.')
(dest/'VERIFICATION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
