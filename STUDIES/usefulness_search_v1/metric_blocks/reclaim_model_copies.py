import hashlib,json
from pathlib import Path
base=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030')
root=base/'work/ablation01'
receipt=json.loads((root/'PARENT-S3-VERIFICATION.json').read_text())
assert receipt['verified_members']==408 and receipt['sha256']=='a745dac01daf953d60b6f52f19c22516f289ffd0a8e55b6b6e066bfc5df35b13'
manifest=json.loads((base/'work/model01/EVIDENCE-MANIFEST.json').read_text())
paths=list((base/'evidence/model01').glob('*/RESULT.json'));verified=[]
for p in paths:
    assert p.resolve().is_relative_to((base/'evidence/model01').resolve())
    key='runs/'+p.parent.name+'/RESULT.json';expected=manifest[key]
    original=base/'work/model01'/key
    assert original.is_file() and hashlib.sha256(original.read_bytes()).hexdigest()==expected['sha256']
    assert p.stat().st_size==expected['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==expected['sha256']
    verified.append(dict(path=str(p),**expected))
assert len(verified)>0
for p in paths:p.unlink()
audit=dict(files=verified,bytes=sum(v['bytes'] for v in verified),s3_version=receipt['version_id'],
    retained_originals=str(base/'work/model01/runs'),reason='Reclaim verified redundant result copies to preserve root disk floor')
for dest in [root/'RECLAIM.json',base/'evidence/RECLAIM-model-results.json']:
    dest.write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps(dict(files=len(paths),bytes=audit['bytes'])))
