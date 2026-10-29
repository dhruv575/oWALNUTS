"""Verify every archived byte without extracting paths or trusting metadata."""
import gzip,hashlib,json,sys,tarfile
from pathlib import Path,PurePosixPath

path=Path(sys.argv[1]);expected=sys.argv[2]
assert hashlib.file_digest(path.open('rb'),'sha256').hexdigest()==expected
manifest=None;names=set();freezes=[]
row_hashes={}
if len(sys.argv)>3:
    for p in Path(sys.argv[3]).glob('*-ROWS.json.gz'):
        for prefix in ('analysis-v1','native-analysis-v1','native-analysis-v2'):
            if p.name.startswith(prefix+'-'):
                member=prefix+'/'+p.name[len(prefix)+1:-3]
                with gzip.open(p,'rb') as f:row_hashes[member]=hashlib.file_digest(f,'sha256').hexdigest()
with tarfile.open(path,'r|gz') as tar:
    for m in tar:
        assert m.name not in names and m.isfile()
        assert not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts
        names.add(m.name);stream=tar.extractfile(m)
        if m.name=='EVIDENCE-MANIFEST.json':manifest=json.load(stream);continue
        assert manifest is not None
        if m.name.endswith('/MANIFEST.json'):
            data=stream.read();obj=json.loads(data);digest=hashlib.sha256(data).hexdigest()
            if 'sources' in obj:freezes.append((m.name,obj['sources']))
        else:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        assert manifest[m.name]==dict(bytes=m.size,sha256=digest),m.name
assert names==set(manifest)|{'EVIDENCE-MANIFEST.json'}
for name,digest in row_hashes.items():assert manifest[name]['sha256']==digest,name
checked=[]
for name,sources in freezes:
    for p,digest in sources.items():
        rel=p.split('/geometry-precision-20261029/')[-1] if p.startswith('/') else 'source/'+p
        assert manifest[rel]['sha256']==digest,(name,rel)
    checked.append(name)
print(json.dumps(dict(sha256=expected,bytes=path.stat().st_size,verified_manifest_members=len(manifest),verified_source_freezes=checked,verified_committed_row_files=len(row_hashes),s3_status='Pending expired local AWS login; remote originals retained'),indent=2))
