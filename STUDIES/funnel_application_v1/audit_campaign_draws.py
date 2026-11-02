"""Recompute physical means and old/new trajectory parity from retained draws."""
import json
import sys
from pathlib import Path

import numpy as np

root = Path(sys.argv[1])
count = 0
maximum = 0.
parity = []
for path in root.rglob('artifact/DRAWS.npz'):
    result = json.loads((path.parent / 'SUMMARY.json').read_text())
    assert result['space'] in ['noncentered', 'hybrid']
    q = np.load(path)['q']
    assert q.shape == (4, result['draws'], 14) and np.isfinite(q).all()
    tau = np.exp(q[..., 1:2])
    theta = q[..., 2:].copy()
    data = json.loads((root / (result['case'] + '.json')).read_text())
    nc = np.ones(12, dtype=bool) if result['space'] == 'noncentered' else np.array(data['n']) < 1000
    theta[..., nc] = q[..., :1] + tau * theta[..., nc]
    values = np.concatenate([q[..., :1], tau, theta, 1 / (1 + np.exp(-theta)),
                             tau < .1, tau < .5], axis=-1)
    difference = float(np.max(np.abs(values.mean((0, 1)) - result['summary']['mean'])))
    assert difference < 1e-10
    maximum = max(maximum, difference)
    count += 1
    if result['engine'] == 'walnuts_latest':
        old = Path(str(path).replace('walnuts_latest', 'walnuts_old'))
        if old.exists():
            parity.append(dict(run=path.parent.parent.name,
                               bit_identical=bool(np.array_equal(q, np.load(old)['q']))))
output = dict(verified=count, max_absolute_mean_difference=maximum, paired_draws=parity)
(root.parent / (root.name + '-RAW-AUDIT.json')).write_text(json.dumps(output, indent=2))
print(json.dumps(dict(verified=count, max_difference=maximum,
                     paired=len(parity), identical=sum(r['bit_identical'] for r in parity))))
