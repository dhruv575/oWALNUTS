import hashlib,json,platform,sys,tarfile
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parent;out=root/'hybrid_analysis_archive';out.mkdir(exist_ok=False)
result=json.loads((root/'HYBRID-COMPARISON.json').read_text())
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in result['inputs'].items())
names=['HYBRID-COMPARISON.json','HYBRID-REPORT.md','HYBRID-VALIDATION.md','HYBRID-TIMING-AUDIT.md','HYBRID-RELATED-WORK.md',
 'HYBRID-UNIT-CHECKS.json','analyze_hybrid.py','verify_hybrid.py','archive_hybrid_analysis.py','hybrid_gate.py','hybrid_prepare.py','run_hybrid.py','test_hybrid_gate.py']
for i in range(1,5):
    names.extend([f'hybrid0{i}/'+n for n in ['SUMMARY.json','VERIFICATION.json','RECLAIM.json']])
    names.extend([f'hybrid0{i}_archive/'+n for n in ['S3-UPLOAD.json','S3-VERIFICATION.json']])
files=[root/n for n in names]
env=out/'ANALYSIS-ENVIRONMENT.json';env.write_text(json.dumps(dict(python=sys.version,platform=platform.platform(),numpy=np.__version__),indent=2)+'\n')
manifest={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files}
manifest['ANALYSIS-ENVIRONMENT.json']=dict(bytes=env.stat().st_size,sha256=hashlib.sha256(env.read_bytes()).hexdigest())
mp=out/'EVIDENCE-MANIFEST.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
archive=out/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    tar.add(mp,arcname=mp.name);tar.add(env,arcname=env.name)
    for p in files:tar.add(p,arcname=p.relative_to(root).as_posix())
print(json.dumps(dict(members=len(manifest),bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest())))
