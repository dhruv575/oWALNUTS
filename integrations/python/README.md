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
rows = result.summary()             # list of dicts: mean, sd, mcse_mean, q5/q50/q95,
                                    # ess_bulk, ess_tail, rhat (owalnuts::diagnostics)
result.health()                     # pooled divergences, depth-cap stops, target calls, ...
idata = result.to_inferencedata()   # arviz InferenceData with sample_stats
```

`summary()` is the Rust `owalnuts::diagnostics` estimator set (rank-normalised
folded split R-hat, bulk/tail ESS, MCSE; matches `az.rhat`/`az.ess`/`az.mcse`
to 1e-6 relative) with no pandas dependency; `owalnuts.summary(samples,
names)` does the same for any `(chains, draws, dim)` array.

Starts: `init=None` draws independent uniform(-2, 2) starts in numpy;
`init=q0` jitters one point per chain; `init="uniform"` is Stan's rule as
implemented by `owalnuts::sampler::Init::uniform` — uniform(-`init_radius`,
`init_radius`) redrawn up to `init_max_attempts` times per chain until the
log density and gradient are finite, deterministic given `seed`
(`owalnuts.uniform_starts(target, dim, chains=4, seed=1)` returns the
starts without sampling).

Defaults follow `owalnuts::sampler::Tuning::default()`: macro step
`h = 0.5`, maximum tree depth 10 (Stan's default; the 0.1 package used 8,
chosen by `STUDIES/adaptation_parity_v1`), four refinement levels,
`delta = 1`; dual-averaging warmup at target acceptance 0.8 with a diagonal
metric. Pass `tuning=owalnuts.Tuning(step_size=0.1, max_depth=8)` for the
0.1 package's behaviour. At depth 10 the exact worst-case evaluation count
of four chains x a few thousand transitions exceeds the facade's
conservative 113M preflight ceiling, so `sample` admits such runs with
their exact worst case by default (`admit_worst_case=True`, the Rust
`Limits::admit_worst_case`); `max_target_evaluations=N` is an exact runtime
ceiling instead, and `admit_worst_case=False` restores the conservative
admission.

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
`Adaptation(paper=owalnuts.PaperAdaptation())`; since 0.2.0 its defaults are
the Rust `PaperAdaptationConfig::default()` v4
(`walnutpie-paper-adaptation-kquantile-gamma-v4`: exhausted transitions count
as unrefined and the step band is 1e6), which is robust on the posteriordb
cells where v3 froze (`STUDIES/paper_adaptation_robust_v1`).

The extension builds the crate with the `research` Cargo feature (needed
for the raised evaluation ceiling behind `max_target_evaluations`).

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

## GIL-free compiled targets

```python
import numba, owalnuts

sig = owalnuts.numba_raw_signature()  # float64(intp, double*, double*, void*)

@numba.cfunc(sig, nopython=True)
def logp_grad(dim, q_ptr, grad_ptr, user_data):
    q = numba.carray(q_ptr, (3,))
    g = numba.carray(grad_ptr, (3,))
    total = 0.0
    for i in range(3):
        g[i] = -q[i]
        total += q[i] * q[i]
    return -0.5 * total   # return -inf for zero-density points

target = owalnuts.from_cfunc(logp_grad, 3)
result = owalnuts.sample(target, 3, threads=4)   # real parallel chains
```

PyMC models get the same transport with
`owalnuts.from_pymc(model, gil_free=True)` (numba required; verified against
the ordinary compiled path before use; shared-variable values are
snapshotted at compile time). Measured on Eight Schools: ~31,000 min-bulk
ESS/s at 4 threads — parity with nutpie — vs ~2,300 through the GIL path.
The callback must be thread-safe, deterministic, write every gradient
element on finite returns, and never raise across the ABI.

## Example: stochastic volatility on the top-5 cryptocurrencies

`examples/crypto_sv.ipynb` (executed notebook) and `examples/crypto_sv.py`
sample the full posterior of a standard SV model over up to 3,153 daily
returns of BTC/ETH/XRP/BNB/SOL through `from_pymc(model, gil_free=True)` with
a tridiagonal-precision path metric — seconds of wall time, zero divergences,
cross-checked against nutpie and NumPyro in the preregistered study
`STUDIES/flagship_crypto_sv_v1` (which also carries the honest limitations:
the shared global-ridge bottleneck and two backends' stuck seeds).
