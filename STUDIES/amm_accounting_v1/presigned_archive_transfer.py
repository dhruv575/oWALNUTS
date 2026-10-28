"""Direct HTTPS archive PUT / exact-version streaming GET without logging URLs."""
import hashlib,json,sys,time,urllib.request,urllib.error
from pathlib import Path

def run(mode,secret_path,archive_path,receipt_path):
    secret_path=Path(secret_path);spec=json.loads(secret_path.read_text());start=time.monotonic()
    expected=spec['sha256'];size=spec['bytes'];receipt=Path(receipt_path)
    if receipt.exists():raise FileExistsError('Receipt exists; inspect before retry')
    if mode=='upload':
        p=Path(archive_path)
        if p.stat().st_size!=size:raise ValueError('Archive size changed')
        with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        if digest!=expected:raise ValueError('Archive hash changed')
        with p.open('rb') as f:
            req=urllib.request.Request(spec['url'],data=f,method='PUT',headers={'Content-Length':str(size),'x-amz-server-side-encryption':'AES256'})
            with urllib.request.urlopen(req,timeout=300) as response:
                if response.status!=200:raise ValueError('Upload status')
                version=response.headers.get('x-amz-version-id');encryption=response.headers.get('x-amz-server-side-encryption');response.read()
        if not version or version=='null' or encryption!='AES256':raise ValueError('Version/encryption admission')
        r=dict(operation='upload',bucket=spec['bucket'],key=spec['key'],version_id=version,sha256=digest,bytes=size,encryption=encryption)
    elif mode=='verify':
        digest=hashlib.sha256();count=0
        with urllib.request.urlopen(spec['url'],timeout=300) as response:
            if response.status!=200 or response.headers.get('x-amz-version-id')!=spec['version_id']:raise ValueError('Exact version/status mismatch')
            if int(response.headers['Content-Length'])!=size:raise ValueError('Response size mismatch')
            while True:
                data=response.read(1024*1024)
                if not data:break
                count+=len(data);digest.update(data)
        if count!=size or digest.hexdigest()!=expected:raise ValueError('Restored byte/hash mismatch')
        r=dict(operation='verify',bucket=spec['bucket'],key=spec['key'],version_id=spec['version_id'],sha256=expected,bytes=count,exact_version_restore_verified=True,verification_location='Existing AWS EC2 instance; full HTTPS response streamed through SHA256 without disk duplication')
    else:raise ValueError('Mode')
    r['elapsed_seconds']=time.monotonic()-start
    with receipt.open('x') as f:json.dump(r,f,indent=2);f.write('\n')
    secret_path.unlink();print(json.dumps(r));return 0

def main():
    try:return run(*sys.argv[1:])
    except urllib.error.HTTPError as exc:
        print(json.dumps(dict(status='failed',error_type=type(exc).__name__,http_status=exc.code)));return 1
    except Exception as exc:
        # Do not print exception text: network libraries may embed the signed URL.
        print(json.dumps(dict(status='failed',error_type=type(exc).__name__)));return 1

if __name__=='__main__':sys.exit(main())
