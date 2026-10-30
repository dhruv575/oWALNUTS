"""Upload immutable evidence; restore its exact S3 version and verify all members."""
import base64,hashlib,json,subprocess,sys,tarfile
from pathlib import Path
archive=Path(sys.argv[1]);report=Path(sys.argv[2]);label=sys.argv[3]
bucket='owalnuts-research-712710405275-us-east-2';digest=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest();checksum=base64.b64encode(bytes.fromhex(digest)).decode()
key=f'research/pharma-ode/20261029/{label}/{digest}.tar.gz';receipt_path=report/'S3-VERIFICATION.json'
def aws(*args):return json.loads(subprocess.check_output(['aws','--profile','owalnuts','--region','us-east-2','s3api',*args,'--output','json'],text=True))
public=aws('get-public-access-block','--bucket',bucket)['PublicAccessBlockConfiguration'];assert all(public.values())
assert aws('get-bucket-versioning','--bucket',bucket)['Status']=='Enabled'
receipt=aws('put-object','--bucket',bucket,'--key',key,'--body',str(archive),'--if-none-match','*','--server-side-encryption','AES256','--checksum-algorithm','SHA256','--checksum-sha256',checksum,'--metadata','sha256='+digest)
assert receipt['ChecksumSHA256']==checksum and receipt['ServerSideEncryption']=='AES256';version=receipt['VersionId']
(report/'S3-UPLOAD.json').write_text(json.dumps(dict(bucket=bucket,key=key,sha256=digest,receipt=receipt),indent=2)+'\n')
restore=archive.with_name(archive.stem+'-s3-restored.tar.gz');assert not restore.exists()
got=aws('get-object','--bucket',bucket,'--key',key,'--version-id',version,'--checksum-mode','ENABLED',str(restore))
assert got['VersionId']==version and got['ChecksumSHA256']==checksum
assert hashlib.file_digest(restore.open('rb'),'sha256').hexdigest()==digest
names=set();manifest=None
with tarfile.open(restore,'r|gz') as tar:
    for m in tar:
        assert m.isfile() and m.name not in names;names.add(m.name);stream=tar.extractfile(m)
        if m.name=='EVIDENCE-MANIFEST.json':manifest=json.load(stream);continue
        assert manifest is not None and manifest[m.name]==dict(bytes=m.size,sha256=hashlib.file_digest(stream,'sha256').hexdigest()),m.name
assert names==set(manifest)|{'EVIDENCE-MANIFEST.json'}
result=dict(bucket=bucket,key=key,version_id=version,sha256=digest,checksum_sha256=checksum,bytes=archive.stat().st_size,restored_path=str(restore),verified_members=len(manifest),private_public_access_block=public,encryption=got['ServerSideEncryption'],remote_originals_retained=True)
receipt_path.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
