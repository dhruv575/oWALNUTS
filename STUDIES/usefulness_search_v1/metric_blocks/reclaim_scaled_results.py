import gzip,hashlib,json,re,sys
from pathlib import Path
base=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030');label=sys.argv[1]
assert re.fullmatch(r'scaled0[1-8]',label)
root=base/'work'/label;evidence=base/'evidence'/label
assert (root/'SUMMARY.json').exists()
assert all(json.loads(p.read_text())['group_drained'] for p in (root/'runs').glob('*/SUPERVISION.json'))
receipt=json.loads(Path(sys.argv[2]).read_text());tar=base/'work'/(label+'-evidence.tar.gz')
assert hashlib.sha256(tar.read_bytes()).hexdigest()==receipt['sha256']
manifest=json.loads((root/'EVIDENCE-MANIFEST.json').read_text());assert len(manifest)==receipt['verified_members']
paths=sorted(evidence.glob('*/RESULT.json.gz'));verified=[];assert paths
for p in paths:
    assert p.resolve().is_relative_to(evidence.resolve())
    key='runs/'+p.parent.name+'/RESULT.json';entry=manifest[key];compressed=p.read_bytes();raw=gzip.decompress(compressed)
    durable=json.loads((p.parent/'MANIFEST.json').read_text())['RESULT.json']
    assert hashlib.sha256(compressed).hexdigest()==durable['gzip_sha256']
    assert len(raw)==entry['bytes'] and hashlib.sha256(raw).hexdigest()==entry['sha256']
    assert hashlib.sha256((root/key).read_bytes()).hexdigest()==entry['sha256']
    verified.append(dict(path=str(p),compressed_bytes=len(compressed),raw_sha256=entry['sha256']))
audit=dict(label=label,s3_version=receipt['version_id'],files=verified,bytes=sum(x['compressed_bytes'] for x in verified),
    retained_originals=str(root/'runs'),reason='Exact verified redundant result files; all original raw evidence and private archive retained')
# Pre-delete audit plus final completion record; no recursive deletion.
dest=base/'evidence'/(label+'-RECLAIM.json');dest.write_text(json.dumps(dict(audit,completed=False),indent=2)+'\n')
for p in paths:p.unlink()
dest.write_text(json.dumps(dict(audit,completed=True),indent=2)+'\n')
print(json.dumps(dict(label=label,files=len(paths),bytes=audit['bytes'],audit=str(dest))))

