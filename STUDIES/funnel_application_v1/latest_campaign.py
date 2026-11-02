import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, '/home/ubuntu/lanes/funnel-application-20261101')
from resource_monitor import execute

BASE = Path(__file__).resolve().parent

if __name__ == '__main__':
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    assert shutil.disk_usage('/home/ubuntu').free > 1024**3
    frozen = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in BASE.rglob('*') if p.is_file() and p.suffix in ['.py', '.json', '.md']}
    (BASE / 'FREEZE.json').write_text(json.dumps(frozen, indent=2))
    rows = []
    for index, case in enumerate(['mixed', 'mixed10', 'mixed100']):
        reference = json.loads((BASE / 'references' / (case + '.json')).read_text())
        if not reference['passed']:
            continue
        for rep in range(1, 5):
            seed = 956800000 + 10 * (index + 1) + rep
            engines = ['walnuts_old', 'walnuts_latest', 'nuts']
            engines = engines[rep % 3:] + engines[:rep % 3]
            for draws in [4000, 8000, 16000]:
                for engine in engines:
                    assert shutil.disk_usage('/home/ubuntu').free > 1024**3
                    accept = .999 if engine == 'nuts' else .9
                    out = BASE / 'runs' / f'{case}-{engine}-{seed}-{draws}'
                    out.mkdir(parents=True)
                    result = execute(
                        ['/home/ubuntu/venv/bin/python', str(BASE / 'latest_worker.py'),
                         case, engine, 'noncentered', str(accept), str(seed),
                         f'budget_{draws}', str(out / 'artifact')],
                        BASE, 900, BASE, 2 * 1024**3, 512 * 1024**2,
                        out / 'worker.log', output_scan_interval=2.)
                    (out / 'SUPERVISION.json').write_text(json.dumps(result, indent=2))
                    if result['exit_code'] != 0 or result['status'] != 'exited':
                        raise RuntimeError(result)
                    rows.append(json.loads((out / 'artifact/SUMMARY.json').read_text()))
                    (BASE / 'PROGRESS.json').write_text(json.dumps({'completed': len(rows)}))
    assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest() == h for n, h in frozen.items())
    (BASE / 'STATUS.json').write_text(json.dumps({'status': 'completed', 'results': rows}, indent=2))
