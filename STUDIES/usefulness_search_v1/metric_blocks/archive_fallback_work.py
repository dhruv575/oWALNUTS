import hashlib,json,shutil,sys,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent;label=root.name;assert label in ['fallbackaudit01','scalerepair01']
s=json.loads((root/'SUMMARY.json').read_text());assert s['unchanged']
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in s['inputs'].items())
if label=='fallbackaudit01':
    assert len(s['rows'])==96 and all('preferred' in r for r in s['rows'])
    assert json.loads((root/'SUPERVISION.json').read_text())['group_drained']
    assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in s['sources'].items())
    size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file());assert size<64*1024**2
    (root/'OUTPUT-SCOPE-AUDIT.json').write_text(json.dumps(dict(final_worker_root_bytes=size,below_64MiB=True,
        limitation='Harness sampled only monitor directory; actual final whole-root bytes audited separately. Future harnesses must monitor worker root.'),indent=2)+'\n')
else:assert json.loads((root/'VERIFICATION.json').read_text())['passed']
for name in ['ENVIRONMENT.json','resource_monitor.py']:
    shutil.copy2(root.parent/'broad01'/name,root/name)
if label=='fallbackaudit01':
    ref=Path('/home/ubuntu/infra/posteriordb/posterior_database/reference_posteriors/draws/draws/sblrc-blr.json.zip');shutil.copy2(ref,root/ref.name)
    shutil.copy2(root.parent/'fisher04/mpmath-1.3.0-py3-none-any.whl',root/'mpmath-1.3.0-py3-none-any.whl')
else:
    shutil.copy2(root.parent/'broad01/REFERENCES.json',root/'REFERENCES.json')
    shutil.copy2(root.parent/'broad01/online-binary',root/'online-binary')
files=sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='EVIDENCE-MANIFEST.json')
manifest={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files}
mp=root/'EVIDENCE-MANIFEST.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
out=root.parent/(label+'-evidence.tar.gz');assert not out.exists()
with tarfile.open(out,'w:gz') as tar:
    tar.add(mp,arcname=mp.name)
    for p in files:tar.add(p,arcname=p.relative_to(root).as_posix())
print(json.dumps(dict(members=len(files),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest())))
