"""Verify full archives plus dependencies against the already verified ODE archive."""
import gzip,hashlib,json,subprocess,sys,tarfile
from pathlib import Path,PurePosixPath
root,label=sys.argv[1:];out=Path('target')/f'usefulness-{label}-evidence.tar.gz';report=Path('STUDIES/usefulness_search_v1')/f'archive-{label}';report.mkdir(exist_ok=True)
oldroot='/home/ubuntu/lanes/pharma-ode-logforecast-20261029';prior=Path('target/pharma-ode-corrected-evidence.tar.gz');prior_receipt=json.loads(Path('STUDIES/pharma_ode_v1/results-20261029/corrected/ARCHIVE-VERIFICATION.json').read_text())
assert hashlib.file_digest(prior.open('rb'),'sha256').hexdigest()==prior_receipt['sha256']
with tarfile.open(prior,'r|gz') as tar:
    first=next(iter(tar));assert first.name=='EVIDENCE-MANIFEST.json';prior_bytes=tar.extractfile(first).read();assert hashlib.sha256(prior_bytes).hexdigest()==prior_receipt['manifest_sha256'];prior_manifest=json.loads(prior_bytes)
cmd=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','HostKeyAlias=18.188.57.71','-i','C:/Users/dhruv/.ssh/owalnuts-bench.pem','ubuntu@18.223.162.103','python3',root+'/packaging/stream_archive.py',root]
with out.open('xb') as f:result=subprocess.run(cmd,stdout=f,stderr=subprocess.PIPE,check=True)
remote=json.loads(result.stderr.decode());names=set();manifest=None;dependencies=[]
with tarfile.open(out,'r|gz') as tar:
    for m in tar:
        assert m.isfile() and m.name not in names and not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts
        names.add(m.name);stream=tar.extractfile(m)
        if m.name=='EVIDENCE-MANIFEST.json':
            raw=stream.read();assert hashlib.sha256(raw).hexdigest()==remote['manifest_sha256'];manifest=json.loads(raw);continue
        keep='/' not in m.name or m.name.endswith(('/MANIFEST.json','/FINAL.json','/SUMMARY.json','/ROWS.json','/INPUT-HASHES.json','/ANALYSIS-HASH.json','/COMPLETE.json','/AUDIT.json'))
        if keep:
            raw=stream.read();digest=hashlib.sha256(raw).hexdigest()
            if m.name.endswith('/MANIFEST.json'):
                d=json.loads(raw)
                if 'dependencies' in d:dependencies.append((m.name,d['dependencies']))
            if m.name.endswith('/INPUT-HASHES.json'):dependencies.append((m.name,json.loads(raw)))
            dest=report/m.name;dest.parent.mkdir(parents=True,exist_ok=True)
            if m.name.endswith('/ROWS.json'):
                with gzip.open(str(dest)+'.gz','wb') as f:f.write(raw)
            else:dest.write_bytes(raw)
        else:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        assert manifest[m.name]==dict(bytes=m.size,sha256=digest),m.name
assert names==set(manifest)|{'EVIDENCE-MANIFEST.json'} and len(manifest)==remote['members']
external=0
screenroot='/home/ubuntu/lanes/usefulness-search-20261029'
screen_manifest=None
screen_receipt=None
if root!=screenroot:
    screen_receipt=json.loads(Path('STUDIES/usefulness_search_v1/archive-screen-v1/ARCHIVE-VERIFICATION.json').read_text())
    screen_archive=Path(screen_receipt['archive'])
    assert hashlib.file_digest(screen_archive.open('rb'),'sha256').hexdigest()==screen_receipt['sha256']
    with tarfile.open(screen_archive,'r|gz') as tar:
        first=next(iter(tar));assert first.name=='EVIDENCE-MANIFEST.json'
        raw=tar.extractfile(first).read()
        assert hashlib.sha256(raw).hexdigest()==screen_receipt['manifest_sha256']
        screen_manifest=json.loads(raw)
for receipt,dep in dependencies:
    for n,h in dep.items():
        if n.startswith(root+'/'):actual=manifest[n[len(root)+1:]]['sha256']
        elif screen_manifest is not None and n.startswith(screenroot+'/'):
            actual=screen_manifest[n[len(screenroot)+1:]]['sha256'];external+=1
        else:
            assert n.startswith(oldroot+'/'),(receipt,n)
            actual=prior_manifest[n[len(oldroot)+1:]]['sha256'];external+=1
        assert actual==h,(receipt,n)
verified=dict(archive=str(out),sha256=hashlib.file_digest(out.open('rb'),'sha256').hexdigest(),bytes=out.stat().st_size,verified_members=len(manifest),manifest_sha256=remote['manifest_sha256'],verified_dependency_manifests=[x[0] for x in dependencies],external_dependency_checks=external,external_archive_sha256=prior_receipt['sha256'],remote_originals_retained=True)
if screen_receipt:verified['screen_dependency_archive_sha256']=screen_receipt['sha256']
(report/'ARCHIVE-VERIFICATION.json').write_text(json.dumps(verified,indent=2)+'\n');print(json.dumps(verified,indent=2))
