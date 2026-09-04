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
`owalnuts_bridgestan::ReplicatedStanTarget` loads one snapshotted copy per
effective replica and runs with the interpreter detached. Rust metadata
distinguishes effective `threading`, `compiled_threading`, `execution`,
`requested_replicas`, and `effective_replicas`; these fields are retained on `StanTarget`/`SampleResult`
where that backend is used. Positions
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

## GIL-free chains

Every `sample` call releases the GIL for the whole run; the kernel calls
the target from Rust worker threads. A Python callable re-attaches the
interpreter on each call, so those chains are serialised (use `threads=1`).
The built-in native targets and compiled C-ABI callbacks (`from_cfunc`,
`from_pymc(gil_free=True)`) never touch the interpreter and run `threads`
chains in parallel. Off Windows, `from_stan` (BridgeStan, above) does too:

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
