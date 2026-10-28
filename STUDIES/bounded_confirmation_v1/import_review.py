"""Verify compact review against archived manifest without displaying scores."""
import hashlib,json,tarfile,sys
from pathlib import Path

def run(archive,destination,batch):
    batch=int(batch);out=Path(destination);out.mkdir(exist_ok=False);prefix=f'batch-{batch:03d}/'
    with tarfile.open(archive) as tar:
        for member in tar:
            if not member.isfile():continue
            if not member.name.startswith(prefix):raise ValueError('Unexpected review member')
            target=out/member.name
            if not target.resolve().is_relative_to(out.resolve()):raise ValueError('Unsafe member')
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(tar.extractfile(member).read())
    folder=out/prefix;manifest=json.loads((folder/'RAW-MANIFEST.json').read_text());checked=0
    for name,meta in manifest.items():
        p=out/name
        if not p.exists():continue
        if p.stat().st_size!=meta['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('Review hash mismatch')
        checked+=1
    receipt=json.loads((folder/'ARCHIVE-VERIFIED.json').read_text());packed=json.loads((folder/'ARCHIVE-PACKED.json').read_text())
    for key in ['sha256','bytes','plan_sha256','manifest_sha256']:
        if receipt[key]!=packed[key]:raise ValueError('Archive binding mismatch')
    for name,key in [('PLAN.json','plan_sha256'),('RAW-MANIFEST.json','manifest_sha256')]:
        if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=receipt[key]:raise ValueError('Control binding mismatch')
    if not receipt['exact_version_restore_verified']:raise ValueError('Restore not verified')
    (out/'.gitattributes').write_text('* -text\n')
    r=dict(batch=batch,checked_manifest_files=checked,archive_sha256=receipt['sha256'],version_id=receipt['version_id'],scope='Compact local evidence verified against archived file manifest; raw draws remain in exact-version S3 archive; forecast scores not displayed')
    (out/'LOCAL-VERIFICATION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))

if __name__=='__main__':run(*sys.argv[1:])
