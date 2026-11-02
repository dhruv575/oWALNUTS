import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, '/home/ubuntu/lanes/funnel-application-20261101')
from resource_monitor import execute

BASE = Path(__file__).resolve().parent
MAIN = Path('/dev/shm/owalnuts-funnel-latest-20261101')

if __name__ == '__main__':
    deadline = time.monotonic() + 7200
    while not (MAIN / 'STATUS.json').exists():
        if time.monotonic() >= deadline:
            raise TimeoutError('Main campaign did not complete')
        time.sleep(5)
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    frozen = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in BASE.rglob('*') if p.is_file() and p.suffix in ['.py', '.json', '.md']}
    (BASE / 'FREEZE.json').write_text(json.dumps(frozen, indent=2))
    rows = []
    for index, case in enumerate(['mixed', 'mixed10', 'mixed100']):
        for rep in range(1, 5):
            seed = 956800000 + 10 * (index + 1) + rep
            engines = ['nuts', 'walnuts_latest'] if rep % 2 else ['walnuts_latest', 'nuts']
            for engine in engines:
                out = BASE / 'runs' / f'{case}-{engine}-{seed}'
                out.mkdir(parents=True)
                result = execute(
                    ['/home/ubuntu/venv/bin/python', str(BASE / 'latest_worker.py'),
                     case, engine, 'hybrid', str(.999 if engine == 'nuts' else .9),
                     str(seed), 'budget_8000', str(out / 'artifact')],
                    BASE, 900, BASE, 2 * 1024**3, 128 * 1024**2,
                    out / 'worker.log', output_scan_interval=2.)
                (out / 'SUPERVISION.json').write_text(json.dumps(result, indent=2))
                if result['exit_code'] != 0 or result['status'] != 'exited':
                    raise RuntimeError(result)
                rows.append(json.loads((out / 'artifact/SUMMARY.json').read_text()))
                (BASE / 'PROGRESS.json').write_text(json.dumps({'completed': len(rows)}))
    assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest() == h for n, h in frozen.items())
    (BASE / 'STATUS.json').write_text(json.dumps({'status': 'completed', 'results': rows}, indent=2))
