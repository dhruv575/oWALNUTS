import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'bounded_transport01';s=json.loads((r/'SUMMARY.json').read_text());assert s['completed'] and not s['advance'];assert all(x['bulk_passed'] for x in s['rows']);files={}
for name,h in s['inputs'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
a=np.load(r/'PROPOSAL-REGION.npz');old=a['old_singular_values'][:,0];new=a['new_singular_values'][:,0];ratio=new/old;assert np.array_equal(ratio,a['ratio']);assert np.quantile(ratio,[0,.5,.95,1]).tolist()==s['tail']['ratio_quantiles'];posthoc=dict(label='Post-hoc explanatory summaries; not an amended gate',old_quantiles=np.quantile(old,[0,.5,.95,1]).tolist(),new_quantiles=np.quantile(new,[0,.5,.95,1]).tolist(),above_relative_gate_count=int((ratio>.75).sum()),old_above_gate=old[ratio>.75].tolist(),new_above_gate=new[ratio>.75].tolist());(r/'POSTHOC.json').write_text(json.dumps(posthoc,indent=2)+'\n')
for dirname in ['bounded_transport01','bounded_transport_supervision01']:
    for f in (l/dirname).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for name in ['BOUNDED-TRANSPORT-PROTOCOL.md','BOUNDED-TRANSPORT-RESULT.md','bounded_transport.py','screen_bounded_transport.py','run_bounded_transport.py','archive_bounded_transport.py','quadratic_transport.py','local_recovery/gp_transport_tail_audit_archive01/VERIFICATION.json']:files[name]=p/name
out=l/'bounded_transport_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    raw=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        raw=t.extractfile(n).read();assert len(raw)==m['bytes'] and hashlib.sha256(raw).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive, depends on preserved input archives; not off-device');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
