# owalnuts (Python)

oWALNUTS — the within-orbit adaptive leapfrog No-U-Turn sampler — for Python
callables, JAX, PyTorch and PyMC models. The extension is a thin PyO3 wrapper
over the public Rust `walnutpie` facade (kernel revision is exposed as
`owalnuts.ALGORITHM_REVISION`); autodiff comes from the framework you already
use.

## Install (development)

```console
cd integrations/python
python -m venv .venv && .venv\Scripts\pip install maturin numpy
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu .venv\Scripts\maturin develop --release
```

## Use

The lowest common denominator is a callable returning the joint log density
and its gradient at an unconstrained `float64` position:

```python
import numpy as np, owalnuts

def logp_and_grad(q):
    return -0.5 * float(q @ q), -q

result = owalnuts.sample(logp_and_grad, dim=10, warmup=1000, draws=1000, seed=1)
idata = result.to_inferencedata()   # arviz InferenceData with sample_stats
```

Adapters produce that callable from autodiff frameworks:

```python
target = owalnuts.from_jax(logp)                    # jit(value_and_grad), x64
target = owalnuts.from_torch(logp)                  # autograd, float64
target, dim, q0, names, unravel = owalnuts.from_pymc(model)  # compiled logp_dlogp
```

Structured metrics (the state-space "path metric" from the 2026-08-31
research program) are one call:

```python
mass = owalnuts.tridiagonal_precision_mass(diag, off)   # momentum covariance = H
result = owalnuts.sample(target, T, mass=mass,
                         adaptation=owalnuts.Adaptation(adapt_mass=False))
```

Zero-density regions: return `-np.inf` (or raise `owalnuts.ZeroDensityError`)
and the kernel refines the step like the reference implementation instead of
rejecting the transition; `nonfinite="fatal"` makes any nonfinite output fail
the run. Paper Appendix C adaptation is
`Adaptation(paper=owalnuts.PaperAdaptation())`.

## What Python costs (measured; see BENCH.md and bench/artifacts)

The kernel calls the target from Rust worker threads; each call re-attaches
the interpreter, so Python targets are serialised by the GIL — use
`threads=1` for Python targets (`threads=4` on the native targets gives ~3×;
on a numpy target it is *slower*). Per-call overhead on this machine:
native Rust ≈ 0.8 µs, PyMC compiled ≈ 7 µs, numpy ≈ 10–13 µs, JAX jit
dispatch ≈ 30–84 µs, PyTorch autograd ≈ 190–290 µs. ESS per target call is
backend-independent to within Monte-Carlo noise (the kernel is the same);
ESS per second is what the callback overhead taxes.

## Tests

```console
.venv\Scripts\python -m pytest -q
```
