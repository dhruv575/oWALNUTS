"""Binary-safe SSH archive download and full manifest/source verification."""
import gzip,hashlib,json,subprocess,sys,tarfile
from pathlib import Path,PurePosixPath

root='/home/ubuntu/lanes/curvature-scaling-20261029'
out=Path('target/curvature-scaling-evidence-v1.tar.gz')
report=Path('STUDIES/curvature_scaling_v1/results-20261029');report.mkdir(exist_ok=True)
cmd=['ssh','-o','BatchMode=yes','-o','HostKeyAlias=18.188.57.71','-i','C:/Users/dhruv/.ssh/owalnuts-bench.pem','ubuntu@18.223.162.103','python3',root+'/packaging/stream_archive.py',root]
with out.open('xb') as f:
    receipt=subprocess.run(cmd,stdout=f,stderr=subprocess.PIPE,check=True)
remote=json.loads(receipt.stderr.decode().strip())
manifest=None;names=set();freezes=[];summary_hashes={}
with tarfile.open(out,'r|gz') as tar:
    for m in tar:
        assert m.isfile() and m.name not in names and not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts
        names.add(m.name);stream=tar.extractfile(m)
        if m.name=='EVIDENCE-MANIFEST.json':
            data=stream.read();assert hashlib.sha256(data).hexdigest()==remote['manifest_sha256'];manifest=json.loads(data);continue
        assert manifest is not None
        keep=m.name in ('analysis-v1/ROWS.json','analysis-v1/CALIBRATION-ROWS.json','analysis-v1/SUMMARY.json','VALIDATION.txt','SELECTION.json','ENVIRONMENT.json') or m.name.endswith('/MANIFEST.json')
        if keep:
            data=stream.read();digest=hashlib.sha256(data).hexdigest()
            if m.name.endswith('/MANIFEST.json'):
                d=json.loads(data)
                if 'sources' in d:freezes.append((m.name,d))
            elif m.name.endswith('ROWS.json'):
                with gzip.open(report/(Path(m.name).name+'.gz'),'wb') as f:f.write(data)
            else:
                (report/Path(m.name).name).write_bytes(data);summary_hashes[m.name]=digest
        else:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        assert manifest[m.name]==dict(bytes=m.size,sha256=digest),m.name
assert names==set(manifest)|{'EVIDENCE-MANIFEST.json'} and len(manifest)==remote['members']
for name,d in freezes:
    for n,h in d['sources'].items():assert manifest['source/'+n]['sha256']==h,(name,n)
    if d.get('selection_sha256'):assert manifest['SELECTION.json']['sha256']==d['selection_sha256']
result=dict(archive=str(out),sha256=hashlib.file_digest(out.open('rb'),'sha256').hexdigest(),bytes=out.stat().st_size,
    verified_members=len(manifest),manifest_sha256=remote['manifest_sha256'],verified_source_freezes=[n for n,d in freezes],exported_files=summary_hashes,
    remote_originals_retained=True,s3_status='Pending renewal of previously expired local AWS login')
(report/'ARCHIVE-VERIFICATION.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
print(json.dumps(result,indent=2))
