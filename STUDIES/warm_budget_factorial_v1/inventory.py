"""Inventory terminal E72 evidence without dropping unstarted or incomplete jobs.

This is a structural audit, not a posterior-precision analysis. Run on a sealed,
drained campaign copy; never use missing files in a live run as failure evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root, reference):
    root = Path(root)
    supervision = read(root / 'SUPERVISION.json')
    if supervision.get('group_drained') is not True:
        raise ValueError('Terminal process-drain receipt required')
    parent = read(root / 'PARENT.json')
    manifest = read(root / 'MANIFEST.json')
    if sha(root / 'PARENT.json') != manifest['parent_sha256']:
        raise ValueError('Parent identity mismatch')
    for name, expected in manifest['new_sources'].items():
        if sha(root / Path(name).name) != expected:
            raise ValueError('Frozen source mismatch: ' + name)
    refs = read(Path(reference))['rows']
    by_spot = {(r['month'], r['tick']): r['extended'] for r in refs}
    expected_spots = {(m['month'], t) for m in parent['months'] for t in m['reference_ticks']}
    if len(refs) != 24 or len(by_spot) != 24 or set(by_spot) != expected_spots:
        raise ValueError('Reference denominator or identity mismatch')
    if len(parent['months']) != 3 or any(len(m['reference_ticks']) != 8 for m in parent['months']):
        raise ValueError('Unexpected fixed campaign dimensions')
    jobs, spots = [], []
    for j in range(12):
        month = parent['months'][j // 4]
        jobroot = root / 'campaign01' / f'job-{j:02d}'
        candidate = jobroot / 'candidate'
        monitor = read(jobroot / 'MONITOR.json') if (jobroot / 'MONITOR.json').exists() else None
        done = read(candidate / 'DONE.json') if (candidate / 'DONE.json').exists() else None
        records = sorted((candidate / 'records').glob('*.json'))
        ticks, divergences, native_completed, scored_ok = [], 0, 0, 0
        for path in records:
            row = read(path)
            tick = row['tick']
            if path.name != f'{tick:06d}.json' or not 1 <= tick <= month['origins']:
                raise ValueError('Record identity mismatch')
            ticks.append(tick)
            native_completed += row.get('native_status') == 'ok'
            scored_ok += tick in month['reference_ticks'] and row.get('score_status') == 'ok'
            divergences += sum(c['divergences'] for c in row.get('native_health', []))
        if ticks != list(range(1, len(ticks) + 1)):
            raise ValueError('Record gap or duplicate')
        complete = (done is not None and done.get('status') == 'complete'
                    and done.get('native_completed') == month['origins']
                    and len(ticks) == month['origins']
                    and native_completed == month['origins'] and scored_ok == 8
                    and monitor is not None and monitor.get('exit_code') == 0
                    and monitor.get('group_drained') is True)
        jobs.append(dict(job=j, month=month['month'], replicate=(j % 4) // 2,
                         k=(400, 1600)[j % 2], complete=complete,
                         started=jobroot.exists(), planned_updates=month['origins'],
                         recorded_updates=len(ticks), recorded_divergences=divergences,
                         monitor=monitor, done=done))
        for tick in month['reference_ticks']:
            path = candidate / 'records' / f'{tick:06d}.json'
            row = read(path) if path.exists() else None
            available = row is not None and row.get('score_status') == 'ok'
            if available:
                array = candidate / row['arrays']['file']
                if candidate.resolve() not in array.resolve().parents:
                    raise ValueError('Array path escapes candidate directory')
                if sha(array) != row['arrays']['sha256']:
                    raise ValueError('Retained array identity mismatch')
            spots.append(dict(job=j, month=month['month'], tick=tick,
                              reference_pass=by_spot[month['month'], tick]['passed'],
                              available=available,
                              score_status=row.get('score_status') if row else 'missing_record',
                              record_sha256=sha(path) if row else None))
    return dict(scope='Structural terminal inventory; no posterior precision or success claim',
                planned_jobs=12, completed_jobs=sum(j['complete'] for j in jobs),
                planned_spots=96, available_spots=sum(s['available'] for s in spots),
                planned_passing_reference_spots=sum(s['reference_pass'] for s in spots),
                reference_sha256=sha(Path(reference)), supervision=supervision,
                campaign_ledger_present=(root / 'campaign01' / 'FINAL.json').exists(),
                jobs=jobs, spots=spots)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root')
    parser.add_argument('reference')
    parser.add_argument('out')
    args = parser.parse_args()
    result = inventory(args.root, args.reference)
    with Path(args.out).open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(json.dumps({k: v for k, v in result.items() if k not in ('jobs', 'spots', 'supervision')}))
