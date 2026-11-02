"""Upload verified local archives, then restore and hash each exact S3 version."""
import concurrent.futures
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUCKET = 'owalnuts-research-712710405275-us-east-2'
OUT = ROOT / 'target/funnel-closeout-s3-20261102'
COMMON = ['--profile', 'owalnuts', '--region', 'us-east-2']

def aws(*args):
    result = subprocess.run(['aws', *args, *COMMON], check=True, capture_output=True, text=True)
    return json.loads(result.stdout) if result.stdout.strip() else None

def upload(record):
    source = Path(record['archive'])
    digest = record['sha256']
    with source.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == digest
    key = f'evidence/sha256/{digest}/funnel-{source.name}'
    aws('s3', 'cp', str(source), f's3://{BUCKET}/{key}', '--sse', 'AES256',
        '--metadata', 'sha256=' + digest, '--only-show-errors')
    head = aws('s3api', 'head-object', '--bucket', BUCKET, '--key', key, '--output', 'json')
    assert head['ContentLength'] == source.stat().st_size and head['Metadata']['sha256'] == digest
    version = head['VersionId']
    restored = OUT / (record['name'] + '.restored.tar.gz')
    aws('s3api', 'get-object', '--bucket', BUCKET, '--key', key,
        '--version-id', version, str(restored), '--output', 'json')
    with restored.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert actual == digest
    receipt = dict(name=record['name'], bucket=BUCKET, key=key, version_id=version,
                   sha256=digest, restored_sha256=actual, bytes=source.stat().st_size,
                   verified=True)
    (OUT / (record['name'] + '.json')).write_text(json.dumps(receipt, indent=2))
    print('Verified S3 archive: ' + record['name'], flush=True)
    return receipt

def main():
    records = json.loads((ROOT / 'research-ops/FUNNEL-CLOSEOUT-ARCHIVES.json').read_text())
    assert shutil.disk_usage(ROOT).free > sum(r['bytes'] for r in records) + 1024**3
    OUT.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(upload, records))
    (ROOT / 'research-ops/FUNNEL-CLOSEOUT-S3-VERIFIED.json').write_text(json.dumps(receipts, indent=2))

if __name__ == '__main__':
    main()
