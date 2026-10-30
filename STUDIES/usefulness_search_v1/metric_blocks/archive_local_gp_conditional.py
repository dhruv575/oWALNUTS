import hashlib,io,json,tarfile
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_conditional_local01';a=json.loads((r/'ADAPTER.json').read_text())
for name,h in a['original_source_hashes'].items():assert hashlib.sha256((p.parent/'gp_count'/name).read_bytes()).hexdigest()==h
for name,h in a['adapted_hashes'].items():assert hashlib.sha256((r/name).read_bytes()).hexdigest()==h
s=json.loads((r/'CONDITIONAL-PREFLIGHT.json').read_text());assert s['passed'] and s['offset_spread']<1e-6 and s['latent_gradient_max']<1e-5 and s['proposal_log_error']<1e-8
supervision=json.loads((l/'gp_conditional_local_supervision01/SUMMARY.json').read_text());assert supervision['exit_code']==0 and supervision['group_drained']
files={}
for folder in [r,l/'gp_conditional_local_supervision01']:
    for f in folder.rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts:files[str(f.relative_to(p))]=f
for name in ['prepare_local_gp_conditional.py','run_local_gp_conditional.py','archive_local_gp_conditional.py','native_common.py','local_recovery/threaded_targets01/gp_pois_regr-gp_pois_regr/SUMMARY.json']:files[name]=p/name
out=l/'gp_conditional_local_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    raw=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        raw=t.extractfile(n).read();assert len(raw)==m['bytes'] and hashlib.sha256(raw).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local preflight archive; compiled target dependency retained separately; not off-device')
(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
