import gzip,hashlib,json
from pathlib import Path
base=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030');root=base/'work/broad01';audits=[]
for label,count,digest in [
    ('ablation01',427,'c2b574cf14874801f83573ca9e744db8665bcc89e6a4de488a2e99a0afb75738'),
    ('fullshape02',423,'45943a0eb2e5262753a4f05dd50749ffb793adc96e52164318933ef4fb518769')]:
    receipt=json.loads((root/(label+'-S3-VERIFICATION.json')).read_text())
    assert receipt['sha256']==digest and receipt['verified_members']==count
    tar=base/'work'/(label+'-evidence.tar.gz');assert hashlib.sha256(tar.read_bytes()).hexdigest()==digest
    manifest=json.loads((base/'work'/label/'EVIDENCE-MANIFEST.json').read_text())
    evidence=base/'evidence'/label;paths=list(evidence.glob('*/RESULT.json.gz'));verified=[]
    for p in paths:
        assert p.resolve().is_relative_to(evidence.resolve())
        key='runs/'+p.parent.name+'/RESULT.json';entry=manifest[key];compressed=p.read_bytes();raw=gzip.decompress(compressed)
        durable=json.loads((p.parent/'MANIFEST.json').read_text())['RESULT.json']
        assert hashlib.sha256(compressed).hexdigest()==durable['gzip_sha256']
        assert len(raw)==entry['bytes'] and hashlib.sha256(raw).hexdigest()==entry['sha256']
        assert hashlib.sha256((base/'work'/label/key).read_bytes()).hexdigest()==entry['sha256']
        verified.append(dict(path=str(p),compressed_bytes=len(compressed),raw_sha256=entry['sha256']))
    assert len(paths)==96
    for p in paths:p.unlink()
    audits.append(dict(label=label,s3_version=receipt['version_id'],files=verified,bytes=sum(x['compressed_bytes'] for x in verified),
        retained_originals=str(base/'work'/label/'runs'),reason='Verified redundant compressed results reclaimed; original manifests retained as historical records'))
for dest in [root/'RECLAIM-GZIP.json',base/'evidence/RECLAIM-GZIP.json']:
    dest.write_text(json.dumps(audits,indent=2)+'\n')
print(json.dumps([dict(label=a['label'],files=len(a['files']),bytes=a['bytes']) for a in audits]))
