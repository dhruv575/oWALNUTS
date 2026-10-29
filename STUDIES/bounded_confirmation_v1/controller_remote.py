"""Operations helper outside the frozen study; no outcome-dependent decisions."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

LANE = Path('/home/ubuntu/lanes/bounded-confirmation-20261028')
SOURCE = LANE / 'source/STUDIES/bounded_confirmation_v1'
CACHE = Path('/home/ubuntu/.cache/owalnuts-transfer')
PYTHON = '/home/ubuntu/lanes/unified-readiness-20261027/installation02/work/env/bin/python'
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(CACHE))


def read(path):
    return json.loads(path.read_text()) if path.exists() else None


def snapshot(batch):
    import psutil
    folder = LANE / f'batch-{batch:03d}'
    live = []
    for p in psutil.process_iter(['pid', 'cmdline']):
        args = p.info['cmdline'] or []
        if str(SOURCE / 'supervisor.py') in args and str(LANE) in args and args[-1] == str(batch):
            live.append(p.info['pid'])
    return dict(exists=folder.exists(), live=live, final=read(folder / 'FINAL.json') is not None,
                supervision=read(folder / 'SUPERVISION.json'),
                packed=read(folder / 'ARCHIVE-PACKED.json'), upload=read(folder / 'UPLOAD.json'),
                restore=read(folder / 'RESTORE.json'), verified=read(folder / 'ARCHIVE-VERIFIED.json'),
                cleaned=read(folder / 'CLEANUP.json'), trimmed=read(folder / 'CONTROLLER-TRIM.json'))


def trim(folder):
    from archive_batch import drained, sha, write
    batch = int(folder.name[-3:])
    drained(folder, batch)
    receipt = read(folder / 'ARCHIVE-VERIFIED.json')
    if not receipt or receipt.get('exact_version_restore_verified') is not True or not receipt.get('version_id'):
        raise ValueError('Verified exact S3 version required')
    for name, field in [('PLAN.json', 'plan_sha256'), ('RAW-MANIFEST.json', 'manifest_sha256')]:
        if sha(folder / name) != receipt[field]:
            raise ValueError('Archive binding drift')
    manifest = read(folder / 'RAW-MANIFEST.json')
    remove = []
    for name, metadata in manifest.items():
        if Path(name).name != 'SAMPLER.json':
            continue
        path = LANE / name
        if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()):
            raise ValueError('Unsafe trim path')
        if not path.exists():
            raise ValueError('Partial trim requires review')
        if path.stat().st_size != metadata['bytes'] or sha(path) != metadata['sha256']:
            raise ValueError('Sampler record drift')
        remove.append(path)
    # These verbose records remain in the verified S3 archive. Keep compact
    # scientific reports, diagnostics, manifests and all failure denominators.
    for path in remove:
        path.unlink()
    write(folder / 'CONTROLLER-TRIM.json', dict(version_id=receipt['version_id'],
          removed=[str(p.relative_to(LANE)) for p in remove], completed=True))


def action(mode, batch, payload):
    from archive_batch import pack, admit, reclaim
    if not 0 <= batch < 255:
        raise ValueError('Batch bounds')
    folder = LANE / f'batch-{batch:03d}'
    state = snapshot(batch)
    if mode == 'status':
        return state
    if state['live']:
        raise ValueError('Live supervisor; no mutation allowed')
    if mode == 'launch':
        if state['exists']:
            raise ValueError('Never rerun an existing batch')
        env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
        with (CACHE / f'controller-launch-{batch:03d}.log').open('xb') as log:
            child = subprocess.Popen([PYTHON, str(SOURCE / 'supervisor.py'), str(LANE), str(batch)],
                cwd=SOURCE, env=env, stdin=subprocess.DEVNULL, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True)
        return dict(launched_pid=child.pid)
    if not state['final'] or not state['supervision']:
        raise ValueError('Incomplete batch requires review')
    if mode == 'pack':
        return state['packed'] or pack(LANE, batch)
    if mode in ('upload', 'verify'):
        from presigned_archive_transfer import run
        name = 'UPLOAD.json' if mode == 'upload' else 'RESTORE.json'
        if (folder / name).exists():
            return read(folder / name)
        packed = state['packed']
        if not packed or any(payload[k] != packed[k] for k in ['bytes', 'sha256']):
            raise ValueError('Transfer identity mismatch')
        fd, secret = tempfile.mkstemp(dir=CACHE, prefix='controller-secret-')
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(payload, f)
            with contextlib.redirect_stdout(io.StringIO()):
                run(mode, secret, LANE / f'batch-{batch:03d}.tar.gz', folder / name)
        finally:
            Path(secret).unlink(missing_ok=True)
        return read(folder / name)
    if mode == 'finish':
        if not state['verified']:
            admit(LANE, batch, folder / 'UPLOAD.json', folder / 'RESTORE.json')
        if not state['cleaned']:
            reclaim(LANE, batch)
        elif state['cleaned'].get('completed') is not True:
            raise ValueError('Partial cleanup requires review')
        if not state['trimmed']:
            trim(folder)
        review = CACHE / f'confirmation-{batch:03d}-controller-review.tar.gz'
        with tarfile.open(review, 'w:gz') as tar:
            for p in sorted(folder.rglob('*')):
                if p.is_file() and 'runtime-cache' not in p.parts:
                    if p.is_symlink():
                        raise ValueError('Symlink in review')
                    tar.add(p, arcname=p.relative_to(LANE), recursive=False)
        return dict(review=str(review), verified=read(folder / 'ARCHIVE-VERIFIED.json'))
    raise ValueError('Unknown operation')


def main():
    import fcntl
    try:
        with (CACHE / 'confirmation-controller.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            payload = json.load(sys.stdin)
            result = action(payload.pop('mode'), int(payload.pop('batch')), payload)
            print(json.dumps(result))
        return 0
    except Exception as exc:
        print(json.dumps(dict(error_type=type(exc).__name__)))
        return 1


if __name__ == '__main__':
    sys.exit(main())
