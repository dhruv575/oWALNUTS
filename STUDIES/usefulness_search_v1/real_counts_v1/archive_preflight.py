import hashlib,json,tarfile
from pathlib import Path
import numpy as np
base=Path(__file__).resolve().parent;raw=base/'preflight_remote01';out=base/'preflight_archive01';out.mkdir(exist_ok=False)
s=json.loads((raw/'SUPERVISION.json').read_text());r=json.loads((raw/'evidence/SUMMARY.json').read_text())
assert s['exit_code']==0 and s['group_drained'] and r['passed'] and r['dimension']==81 and r['functionals']==160
assert r['probe_counts']==dict(value=0,gradient=8,hessian=0,hvp=0)
for q in [np.load(raw/'evidence/NATIVE-SMOKE.npz')['q'],np.asarray(json.loads((raw/'evidence/WAL-RAW.json').read_text())['draws'])]:
    assert q.shape==(4,30,81) and np.isfinite(q).all()
for name in ['preflight.py','GP-TRAIN.json','PREFLIGHT-PROTOCOL.md']:
    expected=r['inputs']['/home/ubuntu/lanes/real-counts-preflight-20261030/'+name]
    assert hashlib.sha256((raw/name).read_bytes()).hexdigest()==expected
files=sorted(p for p in raw.rglob('*') if p.is_file());manifest={str(p.relative_to(raw)):dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files}
archive=out/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as t:
    for p in files:t.add(p,arcname=str(p.relative_to(raw)),recursive=False)
with tarfile.open(archive) as t:
    assert len(t.getmembers())==len(manifest)
    for m in t.getmembers():
        b=t.extractfile(m).read();assert len(b)==manifest[m.name]['bytes'] and hashlib.sha256(b).hexdigest()==manifest[m.name]['sha256']
result=dict(passed=True,members=len(files),archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Finite runtime smoke only; no posterior accuracy qualification',files=manifest)
(out/'VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='files'}))
