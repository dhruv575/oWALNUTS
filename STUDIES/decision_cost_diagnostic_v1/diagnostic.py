"""Complete fixed-grid exploratory arithmetic, using sealed E67 rows only."""
import argparse
import hashlib
import json
import math
from pathlib import Path

MONTHS = {'2026-04': 1440, '2026-05': 1488, '2026-06': 1440}
ARMS = ('candidate', 'ewma_t5', 'rolling_t5')
COSTS = (1, 2, 5, 10, 20, 50, 100, 200)

def loss(m, y, c):
    return c if m > c else y

def integrated(m, y):
    return m*m/2 + (1-m)*y

def analyze(rows):
    output = []
    for bps in COSTS:
        c = bps/10000
        costs = {a: [loss(r['means'][a], r['y'], c) for r in rows] for a in ARMS}
        costs['always_retain'] = [r['y'] for r in rows]
        costs['always_convert'] = [c]*len(rows)
        output.append(dict(cost_bps=bps, arms={a: dict(
            mean_cost=math.fsum(costs[a])/len(rows),
            conversion_rate=sum(r['means'][a] > c for r in rows)/len(rows),
            disagreement_with_candidate=sum((r['means'][a] > c) != (r['means']['candidate'] > c) for r in rows)
        ) for a in ARMS}, advantages={a: math.fsum(x-y for x,y in zip(v,costs['candidate']))/len(rows)
                                     for a,v in costs.items() if a != 'candidate'}))
    identities = {}
    for a in ARMS[1:]:
        direct = math.fsum(integrated(r['means'][a],r['y'])-integrated(r['means']['candidate'],r['y']) for r in rows)/len(rows)
        score = math.fsum(((r['means'][a]-r['y'])**2-(r['means']['candidate']-r['y'])**2)/2 for r in rows)/len(rows)
        if abs(direct-score) > 1e-15:
            raise ValueError('Integrated score identity failed')
        identities[a] = dict(integrated_advantage=direct, half_squared_error_advantage=score)
    return dict(origins=len(rows),cost_grid=output,integrated_identity=identities)

def run(root):
    root = Path(root)
    seal = {}
    for line in (root/'ARTIFACTS.sha256').read_text().splitlines():
        digest,name = line.split(maxsplit=1)
        seal[name.lstrip('*')] = digest
    results, hashes = {}, {}
    for month,n in MONTHS.items():
        rows = []
        for tick in range(1,n+1):
            name = f'campaign01/batch/rows/{month}/{tick:06d}.json'
            raw = (root/name).read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if seal.get(name) != digest:
                raise ValueError('Input seal mismatch: '+name)
            r = json.loads(raw)
            if (r['month'],r['tick']) != (month,tick) or set(r['arms']) != set(ARMS):
                raise ValueError('Row coverage mismatch')
            label = r['label']
            if not math.isfinite(label):
                raise ValueError('Invalid label')
            y = -math.expm1(min(label,0))
            means = {}
            for a in ARMS:
                v = r['arms'][a]
                m = v['mean_downside']
                if v['status'] != 'ok' or not math.isfinite(m) or not 0 <= m <= 1:
                    raise ValueError('Invalid forecast')
                if abs(y-v['score']['realized_downside']) > 1e-14:
                    raise ValueError('Realized loss mismatch')
                means[a] = m
            rows.append(dict(y=y,means=means))
            hashes[name] = digest
        results[month] = analyze(rows)
    return dict(status='complete',scope='Exploratory; no qualification or executable profit claim',
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                input_hashes=hashes,months=results)

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--out',required=True)
    args=p.parse_args();result=run(args.root)
    with Path(args.out).open('x') as f:
        json.dump(result,f,indent=2,allow_nan=False)
