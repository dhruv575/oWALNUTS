"""Independent JAX scan value/gradient check, outside measured processes."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import jax
jax.config.update('jax_enable_x64', True)
import jax.numpy as jnp

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from local_conditional_whitening import jax_log_density

rows = []
for n in [32, 128, 512, 1000]:
    path = HERE / f't{n}.json'
    report = json.loads(path.read_text())
    fn = jax.jit(jax.value_and_grad(lambda q: jax_log_density(q, report['data'])))
    for i, point in enumerate(report['validation_points']):
        value, grad = fn(jnp.asarray(point['position']))
        gradient = np.asarray(grad)
        expected = np.asarray(point['gradient'])
        passed = bool(np.isclose(float(value), point['value'], rtol=1e-10, atol=1e-8)
                      and np.allclose(gradient, expected, rtol=1e-8, atol=1e-7))
        rows.append(dict(periods=n, point=i, passed=passed,
                         value_absolute_error=abs(float(value)-point['value']),
                         gradient_max_absolute_error=float(np.max(np.abs(gradient-expected))),
                         profile_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
result = dict(passed=all(r['passed'] for r in rows), checks=rows,
              scope='Twelve fixed positions; first-order value/gradient parity, not posterior accuracy.',
              validator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              jax=jax.__version__, numpy=np.__version__)
with (HERE / 'gradient-validation.json').open('x') as handle:
    json.dump(result, handle, indent=2, allow_nan=False)
print(json.dumps(result))
raise SystemExit(0 if result['passed'] else 1)
