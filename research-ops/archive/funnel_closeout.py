"""Archive the fixed, completed funnel lanes using the existing instance role."""
import hashlib
import json
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, '/dev/shm/owalnuts-closeout/sdk')
import boto3

BASE = Path('/dev/shm/owalnuts-closeout')
BUCKET = 'owalnuts-research-712710405275-us-east-2'
LANES = [
    Path('/home/ubuntu/lanes/funnel-application-20261101'),
    *[Path('/dev/shm') / ('owalnuts-funnel-' + name + '-20261101') for name in
      ['followup', 'matched', 'conservative', 'serial', 'latest', 'latest-hybrid', 'hybrid-replication']],
]

def main():
    inventory = {}
    for lane in LANES:
        manifest = json.loads((lane / 'ARCHIVE-MANIFEST.json').read_text())
        for name, expected in manifest.items():
            with (lane / name).open('rb') as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == expected, str(lane / name)
        inventory[lane.name] = manifest
    bundle = BASE / 'funnel-closeout.tar.gz'
    with tarfile.open(bundle, 'w:gz', compresslevel=1) as archive:
        for lane in LANES:
            for name in [*inventory[lane.name], 'ARCHIVE-MANIFEST.json']:
                archive.add(lane / name, arcname=lane.name + '/' + name, recursive=False)
    with bundle.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    key = f'evidence/sha256/{digest}/funnel-closeout-20261102.tar.gz'
    client = boto3.client('s3', region_name='us-east-2')
    with bundle.open('rb') as stream:
        response = client.put_object(Bucket=BUCKET, Key=key, Body=stream,
                                     ServerSideEncryption='AES256', Metadata={'sha256': digest})
    version = response['VersionId']
    restored = client.get_object(Bucket=BUCKET, Key=key, VersionId=version)
    verification = hashlib.sha256()
    with restored['Body'] as stream:
        for chunk in iter(lambda: stream.read(8 * 1024**2), b''):
            verification.update(chunk)
    assert verification.hexdigest() == digest
    record = dict(bucket=BUCKET, key=key, version_id=version, sha256=digest,
                  restored_sha256=verification.hexdigest(), bytes=bundle.stat().st_size,
                  lanes=list(inventory), verified=True)
    (BASE / 'S3-VERIFIED.json').write_text(json.dumps(record, indent=2))
    print(json.dumps(record), flush=True)

if __name__ == '__main__':
    main()
