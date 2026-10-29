"""Persistent local coordinator; credentials stay local, research stays on EC2."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / 'target/confirmation-controller'
HOST = 'ubuntu@18.223.162.103'
OPTIONS = ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '-o', 'ServerAliveInterval=15',
           '-o', 'ServerAliveCountMax=4', '-o', 'HostKeyAlias=18.188.57.71',
           '-i', 'C:/Users/dhruv/.ssh/owalnuts-bench.pem']
REMOTE = '/home/ubuntu/.cache/owalnuts-transfer/controller_remote.py'
PYTHON = '/home/ubuntu/lanes/unified-readiness-20261027/installation02/work/env/bin/python'
BUCKET = 'owalnuts-research-712710405275-us-east-2'


def event(**fields):
    value = dict(time_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), pid=os.getpid(), **fields)
    with (STATE / 'events.jsonl').open('a') as f:
        f.write(json.dumps(value) + '\n')
    temporary = STATE / 'status.tmp'
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(STATE / 'status.json')


def remote(mode, batch, **fields):
    try:
        result = subprocess.run(['ssh', *OPTIONS, HOST, f'{PYTHON} {REMOTE}'],
            input=json.dumps(dict(mode=mode, batch=batch, **fields)), text=True,
            capture_output=True, timeout=700)
    except subprocess.TimeoutExpired:
        raise ConnectionError('Remote observation timed out; reconcile before any mutation') from None
    if result.returncode == 255:
        raise ConnectionError('SSH unavailable; remote operation outcome unknown')
    if result.returncode:
        try:
            busy = json.loads(result.stdout).get('error_type') == 'BlockingIOError'
        except (ValueError, AttributeError):
            busy = False
        if busy:
            raise ConnectionError('Remote operation still owns lock')
        # Never print subprocess stderr or signed URLs.
        raise RuntimeError(f'Remote {mode} failed (exit {result.returncode})')
    return json.loads(result.stdout)


def next_action(state):
    if state['live']:
        return 'wait'
    if not state['exists']:
        return 'launch'
    s = state['supervision']
    if not state['final'] or not s or not s.get('group_drained') or not s.get('sources_unchanged'):
        raise ValueError('Incomplete or changed batch requires review; never rerun')
    if state['verified']:
        return 'finish'
    if not state['packed']:
        return 'pack'
    if not state['upload']:
        return 'upload'
    if not state['restore']:
        return 'verify'
    return 'finish'


def transfer_spec(client, packed, batch, upload=None):
    key = f"evidence/sha256/{packed['sha256']}/confirmation-batch-{batch:03d}.tar.gz"
    spec = dict(bucket=BUCKET, key=key, sha256=packed['sha256'], bytes=packed['bytes'])
    params = dict(Bucket=BUCKET, Key=key)
    if upload is None:
        operation = 'put_object'
        params['ServerSideEncryption'] = 'AES256'
    else:
        for k in ['bucket', 'key', 'sha256', 'bytes']:
            if upload[k] != spec[k]:
                raise ValueError('Upload identity mismatch')
        if not upload.get('version_id') or upload['version_id'] == 'null':
            raise ValueError('Version required')
        operation = 'get_object'
        params['VersionId'] = spec['version_id'] = upload['version_id']
    spec['url'] = client.generate_presigned_url(operation, Params=params, ExpiresIn=900)
    return spec


def run():
    import boto3
    from import_review import run as import_review
    session = boto3.Session(profile_name='owalnuts', region_name='us-east-2')
    sts, s3 = session.client('sts'), session.client('s3')
    for batch in range(255):
        while True:
            if (STATE / 'STOP').exists():
                event(state='stopped_at_safe_boundary', batch=batch)
                return
            state = remote('status', batch)
            action = next_action(state)
            event(state=action, batch=batch)
            if action == 'wait':
                time.sleep(15)
                continue
            if action == 'launch':
                if sts.get_caller_identity()['Account'] != '712710405275':
                    raise ValueError('Account mismatch')
                remote('launch', batch)
                time.sleep(3)
            elif action in ('upload', 'verify'):
                remote(action, batch, **transfer_spec(s3, state['packed'], batch,
                       state['upload'] if action == 'verify' else None))
            elif action == 'pack':
                remote('pack', batch)
            else:
                result = remote('finish', batch)
                local = STATE / f'batch-{batch:03d}-review.tar.gz'
                subprocess.run(['scp', *OPTIONS, f"{HOST}:{result['review']}", str(local)],
                               check=True, capture_output=True, timeout=180)
                destination = STATE / f'batch-{batch:03d}-evidence'
                if not destination.exists():
                    import_review(local, destination, batch)
                elif not (destination / 'LOCAL-VERIFICATION.json').exists():
                    raise ValueError('Partial local review requires inspection')
                event(state='batch_preserved', batch=batch, version_id=result['verified']['version_id'])
                break
    event(state='all_255_batches_preserved_no_scores_unsealed')


def main():
    import msvcrt
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'controller.lock').open('a+b') as lock:
        try:
            lock.seek(0)
            if not lock.read(1):
                lock.write(b'0'); lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return 2
        try:
            event(state='starting')
            for attempt in range(21):
                try:
                    run()
                    return 0
                except ConnectionError:
                    if attempt == 20:
                        raise
                    event(state='connection_recovery', attempt=attempt + 1,
                          action='Wait then reconcile remote receipts; never blindly repeat a mutation')
                    time.sleep(30)
        except Exception as exc:
            event(state='blocked', error_type=type(exc).__name__)
            return 1


if __name__ == '__main__':
    sys.exit(main())
