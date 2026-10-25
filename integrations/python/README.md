# owalnuts (Python)

oWALNUTS — the within-orbit adaptive leapfrog No-U-Turn sampler — for Python
callables, JAX, PyTorch, PyMC and Stan models. The extension is a thin PyO3
wrapper over the public Rust `owalnuts::sampler` API (kernel revision is
exposed as `owalnuts.ALGORITHM_REVISION`); autodiff comes from the framework
you already use.

## Install

```console
pip install owalnuts               # numpy only
pip install "owalnuts[stan]"       # + bridgestan: Linux/macOS from_stan
pip install "owalnuts[jax]"        # or [torch], [pymc], [numba], [arviz]
```

Wheels are abi3 (one per platform, CPython 3.10+) for Linux x86_64/aarch64,
macOS x86_64/arm64 and Windows x86_64; anywhere else `pip` builds the sdist
with a Rust 1.88+ toolchain. On Linux/macOS, `[stan]` additionally needs a
C++17 compiler and GNU make (BridgeStan fetches its own Stan sources on first
use). Python `from_stan` is disabled on Windows 0.2 as described below.

### From source

```console
cd integrations/python
python -m venv .venv && .venv\Scripts\pip install maturin numpy
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu .venv\Scripts\maturin develop --release
```

`maturin build --release` produces the wheel, `maturin sdist` the source
distribution (maturin vendors the root crate and `integrations/bridgestan`
into it, so it builds from a clean directory); `.github/workflows/wheels.yml`
does both on every `v*` tag and publishes through PyPI trusted publishing.

## Use

The lowest common denominator is a callable returning the joint log density
and its gradient at an unconstrained `float64` position:

```python
import numpy as np, owalnuts

def logp_and_grad(q):
    return -0.5 * float(q @ q), -q

result = owalnuts.sample(logp_and_grad, dim=10, warmup=1000, draws=1000, seed=1)
print(result)                       # Stan-style table (mean, sd, MCSE, q5/q50/q95,
                                    # bulk/tail ESS, R-hat) plus one health line
rows = result.summary()             # the same rows as a list of dicts
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

Defaults mirror `owalnuts::sampler`: every `sample` call builds a Rust
`Sampler` (`Tuning`, `Adaptation`, `Metric`, `Limits`, `Init`) from its
arguments and sends only what you set, so anything you leave alone is the
sampler default — macro step `h = 0.5`, maximum tree depth 10 (Stan's
default; the 0.1 package used 8, chosen by `STUDIES/adaptation_parity_v1`),
eight refinement levels (`STUDIES/funnel_defaults_v1`: four halve the
funnel's tail mass), `delta = 1`, the momentum-sum no-U-turn rule, Stan's
diagonal-metric prior and the one-sided warmup exhaustion rule of the
post-WP31 default change (`STUDIES/joint_default_v1`,
`STUDIES/posteriordb_bench_v5`), the cached initial evaluation, dual
averaging toward acceptance 0.8 with an adapted diagonal metric, and
worst-case admission. Warmup chain rescue is disabled by default after WP36.
`owalnuts.DEFAULTS` is that set, read from the Rust constants at import
(read-only), including `chain_rescue=None`; `Tuning()` and `Adaptation()`
default from it, and the test suite checks that `sample` with explicit arguments equal to
`DEFAULTS` reproduces a Rust `Sampler` run bit for bit. Pass
`tuning=owalnuts.Tuning(step_size=0.1, max_depth=8)` for the 0.1 package's
tuning, `Tuning(u_turn_rule="endpoints")` with
`Adaptation(metric_regularization="toward_unit")` for the frozen `v10`
kernel rules, and `cache_initial_evaluation=False` for the 0.1 target-call
accounting.

At depth 10 the exact worst-case evaluation count of four chains x a few
thousand transitions exceeds the facade's conservative 113M preflight
ceiling, so `sample` admits such runs with their exact worst case by
default (`admit_worst_case=True`, the Rust `Limits::admit_worst_case`);
`max_target_evaluations=N` is an exact runtime ceiling and the admission
ceiling, and `admit_worst_case=False` restores the conservative admission.
Structured metrics have no budgeted facade path: their ceiling is raised
through the crate's `research` feature (which the extension enables) up to
the hard 1e9 research maximum, so at the defaults a structured-metric run
must keep its worst case under 1e9 (about 2,500 transitions in total; check
with `owalnuts.preflight(dim, mass=...)`) or lower `max_depth`.

Adapters produce that callable from autodiff frameworks:

```python
target = owalnuts.from_jax(logp)                    # jit(value_and_grad), x64
target = owalnuts.from_torch(logp)                  # autograd, float64
target, dim, q0, names, unravel = owalnuts.from_pymc(model)  # compiled logp_dlogp
```

## Stan models

`from_stan` compiles a Stan program with the [BridgeStan](https://github.com/roualdes/bridgestan)
package (`pip install "owalnuts[stan]"`) and samples it GIL-free on Linux and
macOS:

> **Windows 0.2 safety gate:** `from_stan`, `StanTarget.__call__`,
> `StanTarget.model`, `constrained_names`, and `constrain` raise an actionable
> unsupported-platform error. Those operations use the separate Python
> `bridgestan.StanModel` and bypass the Rust owned-worker lifetime backend.
> The Rust `owalnuts-bridgestan` API is the qualified Windows path. `HAS_STAN`
> reports whether the extension was compiled with the feature; it does not
> override this platform gate.

```python
import owalnuts

data = {"J": 8, "y": [28, 8, -3, 7, -1, 1, 18, 12], "sigma": [15, 10, 16, 11, 9, 11, 10, 18]}
target = owalnuts.from_stan("eight_schools.stan", data, seed=1)   # or a built *_model.so
result = owalnuts.sample(target, chains=4, warmup=1000, draws=1000, seed=1, threads=4)

result.summary()                     # rows named by Stan's unconstrained parameters
theta = target.constrain(result)     # (chains, draws, n) constrained draws, bs_param_constrain
target.constrained_names()           # their names; include_tp=/include_gq= as in BridgeStan
```

Off Windows, the library is built **without** `STAN_THREADS` unless
`make_args=["STAN_THREADS=true"]` is passed. The Rust
`owalnuts_bridgestan::ReplicatedStanTarget` keeps replica 0 at the original
model path, copies replicas 1 through n-1, and runs with the interpreter
detached. `StanTarget.compiled_threading` is a library capability;
`probe_threading`, `probe_execution`, `probe_requested_replicas`, and
`probe_effective_replicas` describe only the one-replica metadata probe made
by `from_stan`. They do not predict later sampling. `SampleResult.threading`,
`target_execution`, `requested_replicas`, and `effective_replicas` report the
target actually created for that sampling run. Positions
are Stan's unconstrained parameters (`propto=False, jacobian=True`); a Stan
exception or nonfinite value is a zero-density proposal (refined, then
rejected), as in CmdStan. `data` is a dict (numpy arrays allowed), a
`.json` path or JSON text; `seed` is the Stan model seed, the sampling seed
is `sample(seed=...)`. A `StanTarget` is also a plain `logp_and_grad`
callable through the `bridgestan` package off Windows.

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

## What Python costs (measured; `STUDIES/python_callpath_v1`)

Every path runs the same kernel, so ESS per target call is the same to
Monte-Carlo noise (paths that call the same compiled function give
bit-identical draws); what differs is the cost of one call. Measured on a
contended 16-core Windows machine (walls are relative, not absolute; the
`threads=4` column is the build with the fixes below) on a 100-D Gaussian,
noncentered Eight Schools and a 157-D hierarchical regression, 4 chains x
1,000/1,000 at the defaults:

| path | µs per call in the sampler (gauss / eight / hier) | `threads=4` vs `threads=1` |
|---|---|---|
| `from_cfunc` (numba `cfunc`) | 1.4 / 0.6 / 2.9 | 2.7–3.3x faster |
| `from_pymc(model, gil_free=True)` | 4 / 6 / 24 | 2.5–3x faster (one contended outlier) |
| plain callable calling a numba `njit` kernel | 3.0 / 1.8 / 4.2 | 1.8–3.2x **slower** |
| plain numpy callable | 3.8 / 9.2 / 36 | 1.4–2.3x **slower** |
| `from_pymc(model)` (default: compiled PyTensor C function, a Python callable) | 7 / 12 / 31 | 1.4–3x **slower** (`thread_safe=True`) |
| `from_jax(logp)` | 22 / 19 / 32 | 2.3–3.3x **slower** |
| `from_torch(logp)` | 66 / 290 / 500 | 1.1–2.8x **slower** |

Against nutpie 0.16.8 on the same PyMC models (same chains and draws):
`from_pymc(model)` reaches 0.17–0.24x nutpie's ESS/s at one core;
`from_pymc(model, gil_free=True)` reaches 0.5–1.0x at one core and
0.5–0.9x at four; a hand-written numba `cfunc` (below) is 2–9x nutpie's ESS/s
even though nutpie gets 1.6–2.4x more ESS per gradient on these three models.

Guidance:

* **Python callables (numpy, JAX, PyTorch, the default `from_pymc`): use
  `threads=1`.** A callable holds the GIL, so chains on worker threads queue
  for it, and `threads=4` is slower than `threads=1` for every cheap
  callable. Only a callable that spends most of its time outside the GIL
  (large XLA or PyTorch kernels) can gain.
* **For speed, use a compiled C-ABI target**: `from_pymc(model,
  gil_free=True)` for PyMC models (numba required), or `from_cfunc` for a
  hand-written numba kernel; both run `threads` chains in parallel.
* **Compile numba kernels for `from_cfunc` with `error_model="numpy"`** on
  both the `njit` helpers and the `cfunc`, and return `-inf` (gradient
  zeroed) when the value or any gradient element is nonfinite. Numba's
  default `error_model="python"` raises `ZeroDivisionError` on a float
  division by zero, which cannot cross the C ABI: the call returns garbage
  and the run fails with "raw target wrote a nonfinite gradient element".
  The callable transport hides this (it treats `ZeroDivisionError` and any
  nonfinite output as a zero-density point by default); the raw ABI
  treats a finite value with a nonfinite gradient as fatal.
* `from_jax` calls the jitted `value_and_grad` on the numpy position directly
  (after 0.2.0; 2.0–2.6x ESS/s over 0.2.0's extra `jnp.asarray` dispatch).
  JAX's per-call dispatch (15–30 µs) still dominates small models.
* `from_pymc(model)` is a Python callable around PyMC's compiled
  `logp_dlogp_function` (PyTensor C backend by default), not a compiled
  transport. `thread_safe=True` (one compiled function per worker thread) is
  needed for `threads > 1`; in 0.2.0 it recompiled the PyTensor function
  on every callback at `threads > 1` (a run did not finish), because worker
  threads got a fresh Python thread state per call. After 0.2.0 each worker
  thread keeps one Python thread state for the whole run, so
  `threading.local` state persists and Python callables at `threads=4` are
  1.1–1.9x faster than in 0.2.0 (PyTorch unchanged; all still slower than
  `threads=1`).
* PyTorch's per-call cost is mostly the autograd/dispatcher overhead of
  many small ops; it is the slowest path for small models.

## Tests

```console
.venv\Scripts\python -m pytest -q
```

## GIL-free chains

Every `sample` call releases the GIL for the whole run; at `threads=1` the
chains run on the calling thread, at `threads > 1` on Rust worker threads.
A Python callable re-attaches the interpreter on each call, so those chains
are serialised by the GIL (use `threads=1`; see the table above).
The built-in native targets and compiled C-ABI callbacks (`from_cfunc`,
`from_pymc(gil_free=True)`) never touch the interpreter and run `threads`
chains in parallel. Off Windows, `from_stan` (BridgeStan, above) does too:

```python
import numba, numpy as np, owalnuts

sig = owalnuts.numba_raw_signature()  # float64(intp, double*, double*, void*)

# error_model="numpy": a division by zero gives inf/nan instead of a Python
# exception, which cannot cross the C ABI (use it on njit helpers too).
@numba.cfunc(sig, nopython=True, error_model="numpy")
def logp_grad(dim, q_ptr, grad_ptr, user_data):
    q = numba.carray(q_ptr, (3,))
    g = numba.carray(grad_ptr, (3,))
    total = 0.0
    for i in range(3):
        g[i] = -q[i]
        total += q[i] * q[i]
    value = -0.5 * total
    if not np.isfinite(value) or not np.all(np.isfinite(g)):
        g[:] = 0.0
        return -np.inf   # zero-density point: refined, then rejected
    return value

target = owalnuts.from_cfunc(logp_grad, 3)
result = owalnuts.sample(target, 3, threads=4)   # real parallel chains
```

PyMC models get the same transport with
`owalnuts.from_pymc(model, gil_free=True)` (numba required; verified against
the ordinary compiled path before use). This path uses PyMC's
`freeze_dims_and_data` to compile a separate snapshot of `pm.Data` values and
mutable dimensions. The original model remains updateable: after `pm.set_data`,
an existing target still represents its original data, and calling
`from_pymc(model, gil_free=True)` again creates a target for the new data.
Keep the data unchanged while constructing a target. Shared graph inputs that
the official transform cannot freeze, such as an unregistered
`pytensor.shared` used directly in a potential, are explicitly rejected; use
`pm.Data` or the callable `gil_free=False` path instead. Unsupported snapshot
transforms or changed parameter layouts also fail before sampling.
Nonfinite densities or gradients during proposals
become recoverable zero-density evaluations, matching the callable adapter's
default; an invalid initial point still fails verification.
Measured on Eight Schools: ~31,000 min-bulk
ESS/s at 4 threads — parity with nutpie — vs ~2,300 through the GIL path.
The callback must be thread-safe, deterministic, write every gradient
element on finite returns, and never raise across the ABI (hence
`error_model="numpy"` for numba).

## Example: stochastic volatility on the top-5 cryptocurrencies

`examples/crypto_sv.ipynb` (executed notebook) and `examples/crypto_sv.py`
sample the full posterior of a standard SV model over up to 3,153 daily
returns of BTC/ETH/XRP/BNB/SOL through `from_pymc(model, gil_free=True)` with
a tridiagonal-precision path metric — seconds of wall time, zero divergences,
cross-checked against nutpie and NumPyro in the preregistered study
`STUDIES/flagship_crypto_sv_v1` (which also carries the honest limitations:
the shared global-ridge bottleneck and two backends' stuck seeds).
