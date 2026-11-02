import json
import os
import sys
from pathlib import Path

sys.path.insert(0, '/home/ubuntu/lanes/funnel-application-20261101')
from resource_monitor import execute

BASE = Path(__file__).resolve().parent

if __name__ == '__main__':
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    rows = []
    for index, case in enumerate(['weak', 'mixed']):
        for rep in range(1, 9):
            seed = 956700000 + 10 * (index + 1) + rep
            for draws in [1000, 2000, 4000]:
                engines = ['walnuts', 'nuts'] if rep % 2 else ['nuts', 'walnuts']
                for engine in engines:
                    accept = .9 if engine == 'walnuts' else (.99 if case == 'weak' else .999)
                    out = BASE / f'{case}-{engine}-{seed}-{draws}'
                    out.mkdir()
                    result = execute(
                        ['/home/ubuntu/venv/bin/python', str(BASE / 'budget_worker.py'),
                         case, engine, 'noncentered', str(accept), str(seed),
                         f'budget_{draws}', str(out / 'artifact')],
                        BASE, 900, BASE, 2 * 1024**3, 128 * 1024**2,
                        out / 'worker.log', output_scan_interval=2.)
                    (out / 'SUPERVISION.json').write_text(json.dumps(result, indent=2))
                    if result['exit_code'] != 0:
                        raise RuntimeError(result)
                    rows.append(json.loads((out / 'artifact/SUMMARY.json').read_text()))
                    (BASE / 'PROGRESS.json').write_text(json.dumps({'completed': len(rows)}))
    (BASE / 'STATUS.json').write_text(json.dumps({'status': 'completed', 'results': rows}, indent=2))
