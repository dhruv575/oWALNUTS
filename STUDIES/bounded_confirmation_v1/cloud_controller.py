"""Instance-local operations loop; the frozen scientific workers are unchanged."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, '/home/ubuntu/.cache/owalnuts-transfer/aws-sdk')
import controller_remote as operations
from controller import next_action, transfer_spec

STATE = operations.CACHE / 'cloud-controller'


def event(**fields):
    row = dict(time_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               pid=os.getpid(), **fields)
    with (STATE / 'events.jsonl').open('a') as f:
        f.write(json.dumps(row) + '\n')
    temp = STATE / 'status.tmp'
    temp.write_text(json.dumps(row, indent=2) + '\n')
    temp.replace(STATE / 'status.json')


def transfer(client, batch, packed, upload=None):
    return transfer_spec(client, packed, batch, upload)


def preserve_review(client, batch, review_path):
    from presigned_archive_transfer import run
    path = Path(review_path)
    folder = operations.LANE / f'batch-{batch:03d}'
    if (folder / 'COMPACT-ARCHIVE.json').exists():
        return
    with path.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    spec = dict(bucket='owalnuts-research-712710405275-us-east-2',
                key=f'evidence/sha256/{digest}/confirmation-review-{batch:03d}.tar.gz',
                sha256=digest, bytes=path.stat().st_size)
    upload_path = STATE / f'review-{batch:03d}-upload.json'
    restore_path = STATE / f'review-{batch:03d}-restore.json'
    for mode, receipt in [('upload', upload_path), ('verify', restore_path)]:
        if receipt.exists():
            saved = json.loads(receipt.read_text())
            if saved['sha256'] != digest or saved['bytes'] != spec['bytes']:
                raise ValueError('Compact receipt drift requires review')
            continue
        params = dict(Bucket=spec['bucket'], Key=spec['key'])
        if mode == 'upload':
            operation = 'put_object'; params['ServerSideEncryption'] = 'AES256'
        else:
            operation = 'get_object'
            spec['version_id'] = json.loads(upload_path.read_text())['version_id']
            params['VersionId'] = spec['version_id']
        spec['url'] = client.generate_presigned_url(operation, Params=params, ExpiresIn=900)
        fd, secret = tempfile.mkstemp(dir=STATE)
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(spec, f)
            with contextlib.redirect_stdout(io.StringIO()):
                run(mode, secret, path, receipt)
        finally:
            Path(secret).unlink(missing_ok=True)
    receipt = json.loads(restore_path.read_text())
    if receipt.get('exact_version_restore_verified') is not True:
        raise ValueError('Compact restore required')
    receipt['plan_sha256'] = operations.read(folder / 'ARCHIVE-VERIFIED.json')['plan_sha256']
    with (folder / 'COMPACT-ARCHIVE.json').open('x') as f:
        json.dump(receipt, f, indent=2)


def run(start):
    import boto3
    from botocore.config import Config
    from import_review import run as verify_review
    session = boto3.Session(region_name='us-east-2')
    identity = session.client('sts').get_caller_identity()
    if identity['Account'] != '712710405275' or ':assumed-role/owalnuts-confirmation-archive/' not in identity['Arn']:
        raise ValueError('Dedicated instance role required')
    client = session.client('s3', config=Config(retries={'mode':'standard','max_attempts':4}))
    if start:
        from supervisor import check_previous
        check_previous(operations.LANE, start)
    for batch in range(start, 255):
        while True:
            if (STATE / 'STOP').exists():
                event(state='stopped_at_safe_boundary', batch=batch)
                return
            state = operations.snapshot(batch)
            action = next_action(state)
            event(state=action, batch=batch)
            if action == 'wait':
                time.sleep(2)
            elif action in ('upload','verify'):
                payload = transfer(client, batch, state['packed'],
                                   state['upload'] if action == 'verify' else None)
                operations.action(action, batch, payload)
            elif action == 'finish':
                result = operations.action('finish', batch, {})
                marker = STATE / f'batch-{batch:03d}-review-verification.json'
                if not marker.exists():
                    # Do not accumulate a second expanded copy of every batch.
                    with tempfile.TemporaryDirectory(dir=STATE) as temporary:
                        destination = Path(temporary) / 'evidence'
                        with contextlib.redirect_stdout(io.StringIO()):
                            verify_review(result['review'], destination, batch)
                        marker.write_bytes((destination / 'LOCAL-VERIFICATION.json').read_bytes())
                preserve_review(client, batch, result['review'])
                event(state='batch_preserved', batch=batch, version_id=result['verified']['version_id'])
                break
            else:
                operations.action(action, batch, {})
                if action == 'launch':
                    time.sleep(1)
    event(state='all_255_batches_preserved_no_scores_unsealed')


def main():
    import fcntl
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (operations.CACHE / 'confirmation-controller.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 2
        try:
            start = int(sys.argv[1])
            if not 0 <= start < 255:
                raise ValueError('Batch bounds')
            event(state='starting', batch=start)
            run(start)
            return 0
        except Exception as exc:
            event(state='blocked', error_type=type(exc).__name__)
            return 1


if __name__ == '__main__':
    sys.exit(main())
