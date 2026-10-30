"""Binary-safe full evidence backup with member and source-freeze verification."""
import gzip,hashlib,json,subprocess,sys,tarfile
from pathlib import Path,PurePosixPath
root,label=sys.argv[1:];out=Path('target')/f'pharma-ode-{label}-evidence.tar.gz'
report=Path('STUDIES/pharma_ode_v1/results-20261029')/label;report.mkdir(parents=True,exist_ok=True)
cmd=['ssh','-o','BatchMode=yes','-o','HostKeyAlias=18.188.57.71','-i','C:/Users/dhruv/.ssh/owalnuts-bench.pem','ubuntu@18.223.162.103','python3',root+'/packaging/stream_archive.py',root]
with out.open('xb') as f:receipt=subprocess.run(cmd,stdout=f,stderr=subprocess.PIPE,check=True)
remote=json.loads(receipt.stderr.decode().strip());manifest=None;names=set();freezes=[]
with tarfile.open(out,'r|gz') as tar:
    for m in tar:
        assert m.isfile() and m.name not in names and not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts
        names.add(m.name);stream=tar.extractfile(m)
        if m.name=='EVIDENCE-MANIFEST.json':
            data=stream.read();assert hashlib.sha256(data).hexdigest()==remote['manifest_sha256'];manifest=json.loads(data);continue
        keep='/' not in m.name or m.name.endswith('/MANIFEST.json') or m.name.endswith('/FINAL.json')
        if keep:
            data=stream.read();digest=hashlib.sha256(data).hexdigest()
            if m.name.endswith('/MANIFEST.json'):
                d=json.loads(data)
                if 'sources' in d:freezes.append((m.name,d))
            dest=report/m.name.replace('/','--')
            if m.name.endswith('ROWS.json'):
                with gzip.open(str(dest)+'.gz','wb') as f:f.write(data)
            else:dest.write_bytes(data)
        else:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        assert manifest[m.name]==dict(bytes=m.size,sha256=digest),m.name
assert names==set(manifest)|{'EVIDENCE-MANIFEST.json'} and len(manifest)==remote['members']
verified=[];aborted=[]
for name,d in freezes:
    differences=[n for n,h in d['sources'].items() if manifest[n]['sha256']!=h]
    if name=='initial01/MANIFEST.json' and label=='legacy':
        assert differences==['source/supervisor.py'];aborted.append(dict(manifest=name,known_post_abort_changes=differences));continue
    assert not differences,(name,differences)
    if d.get('selection_sha256'):assert manifest['SELECTION.json']['sha256']==d['selection_sha256']
    verified.append(name)
result=dict(archive=str(out),sha256=hashlib.file_digest(out.open('rb'),'sha256').hexdigest(),bytes=out.stat().st_size,verified_members=len(manifest),manifest_sha256=remote['manifest_sha256'],verified_source_freezes=verified,aborted_attempts=aborted,remote_originals_retained=True,s3_status='Awaiting separate upload and exact-version restore verification')
(report/'ARCHIVE-VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
