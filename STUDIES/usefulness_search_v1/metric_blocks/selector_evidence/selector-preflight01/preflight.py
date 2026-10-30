import hashlib
import json
import time
from pathlib import Path
import numpy as np
from selector import select

root = Path(__file__).resolve().parent
start = time.monotonic()
checks = []
def check(name, condition):
    checks.append(dict(name=name, passed=bool(condition)))

p = np.array([[1., .9, 0], [.9, 1., 0], [0, 0, 1.]])
h = np.array([p*s for s in [1., 10., 100., 1000.]])
v = np.array([2., 3., 4.])
m, info = select(h, h, v)
check('scaled_known_block', info['blocks'] == [[0, 1]] and
      np.allclose(m[0, 1], -.9*np.sqrt(6)) and np.allclose(np.diag(m), v))
for name, q in [
    ('independent', np.tile(np.eye(3), (4, 1, 1))),
    ('indefinite', np.tile([[1., 2., 0], [2., 1., 0], [0, 0, -1.]], (4, 1, 1))),
    ('ill_conditioned', np.tile([[1., 1.-1e-12], [1.-1e-12, 1.]], (4, 1, 1))),
    ('rotating', np.array([[[1., r], [r, 1.]] for r in [-.9, -.3, .3, .9]]))]:
    vv = np.arange(1, q.shape[1]+1, dtype=float)
    mm, ii = select(q, q, vv)
    check(name, np.array_equal(mm, np.diag(vv)) and not ii['blocks'])
mm, ii = select(h*1.01, h, v)
check('inconsistent_derivative', ii['reason'] == 'derivative' and np.array_equal(mm, np.diag(v)))
scale = np.array([.01, 10., 2.])
scaled = h / np.outer(scale, scale)
mm, ii = select(scaled, scaled, v*scale**2)
check('exact_shape_unit_equivariance', np.allclose(mm, m*np.outer(scale, scale)))

raw_path = root/'RAW.json'
raw = json.loads(raw_path.read_text())
rows = []
rng = np.random.default_rng(2026103001)
for cell in raw:
    a = np.array([r['hessian'] for r in cell['records']])
    b = np.array([r['hessian_half_step'] for r in cell['records']])
    d = a.shape[1]
    vv = np.ones(d)
    mm, ii = select(a, b, vv)
    errors = []
    for _ in range(10):
        perm = rng.permutation(d)
        pm, pi = select(a[:, perm, :][:, :, perm], b[:, perm, :][:, :, perm], vv[perm])
        errors.append(float(np.max(np.abs(pm-mm[np.ix_(perm, perm)]))))
        check('permutation_%s_%s_%s' % (cell['model'], cell['seed'], _),
              np.allclose(pm, mm[np.ix_(perm, perm)], atol=1e-10, rtol=1e-10)
              and pi['reason'] == ii['reason'])
    rows.append(dict(model=cell['model'], seed=cell['seed'], selection=ii,
                     permutation_error=max(errors), covariance=mm.tolist()))
out = dict(checks=checks, passed=all(c['passed'] for c in checks), rows=rows,
           seconds=time.monotonic()-start, additional_target_calls=0,
           inputs={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in [raw_path, root/'selector.py', root/'preflight.py',
                             root/'SELECTOR-PREFLIGHT.md']})
(root/'RESULT.json').write_text(json.dumps(out, indent=2, allow_nan=False)+'\n')
print(json.dumps(out))
if not out['passed']:
    raise SystemExit(1)
