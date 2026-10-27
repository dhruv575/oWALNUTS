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
result.chain_warnings()             # observe-only: a chain that disagrees with the others
                                    # (also printed as `warning: chain k ...` lines)
idata = result.to_inferencedata()   # arviz InferenceData with sample_stats
```

`chain_warnings()` is `owalnuts::diagnostics::ChainWarning`: a collapsed
end-of-warmup step, a median log density far below the other chains' at
the end of warmup or over the draws, or a chain whose removal alone brings
R-hat under 1.01 (`STUDIES/chain_disagreement_warning_v1`). The inputs are
each chain dict's `warmup_end` / `sampling_end` and the draws; nothing acts
on them, so the draws are unchanged. It catches one-wrong-chain failures
only and does not replace the R-hat / ESS gates.
It also reports, per chain, nonfinite integrator positions that the default
`RejectLeaf` policy rescued as zero-density leaves (`check ==
"nonfinite_positions"`, with `warmup` and `sampling` counts; printed as
`warning: chain k rejected n nonfinite positions during warmup`). The rescue
records no divergence, so this line is the only place it shows outside the
`work_discarded` / `work_retained` dicts.

`summary()` is the Rust `owalnuts::diagnostics` estimator set (rank-normalised
folded split R-hat, bulk/tail ESS, MCSE; matches `az.rhat`/`az.ess`/`az.mcse`
to 1e-6 relative) with no pandas dependency; `owalnuts.summary(samples,
names)` does the same for any `(chains, draws, dim)` array.

Starts (`owalnuts.START_RULES`; every rule is deterministic given `seed`):

* `init=None` (default) or `init="best_of"` is the Rust default
  `owalnuts::sampler::Init::best_of(16)` (`DEFAULTS["init"]`,
  `DEFAULTS["init_candidates"]`), for callables, `from_cfunc` and Stan
  targets alike. Each chain draws `init_candidates` uniform(-`init_radius`,
  `init_radius`) candidates, redraws each up to `init_max_attempts` times
  until the log density and gradient are finite, and starts at the
  candidate of highest log density. The starts are the Rust sampler's for
  the same seed. The roughly 64 candidate evaluations are not in
  `target_calls`. `owalnuts.best_of_starts(target, dim, chains=4, seed=1,
  return_details=True)` returns the starts with every candidate's log
  density.
* `init="uniform"` is Stan's rule (`Init::uniform`): one evaluable
  uniform(-`init_radius`, `init_radius`) start per chain
  (`owalnuts.uniform_starts`).
* `init="jitter"` draws unchecked numpy uniform(-`init_jitter`,
  `init_jitter`) starts without evaluating the target. This was `init=None`
  up to 0.2.0; use it to reproduce older runs. It can start outside the
  support: in `STUDIES/nutpie_per_gradient_gap_v1` it failed all 12
  `lotka_volterra` runs at transition 0.
* `init=q0` (a `(dim,)` point) jitters it per chain by `init_jitter`, and a
  `(chains, dim)` array is used as given.

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
The trapped-chain guard is on by default since WP90
(`STUDIES/trap_guard_confirmation_v1`): with at least three chains, a
chain whose step size at the close of the first slow warmup window is below
0.01x the chain median restarts from an independent best-of-16 start; the
other chains are untouched, a run in which no chain fires has the same
draws as one without the guard, and each chain's `trapped_chain_checks`
records the check. `Adaptation(trapped_chain_restart=False)` removes it.
`owalnuts.DEFAULTS` is that set, read from the Rust constants at import
(read-only), including `chain_rescue=None` and the guard's rule under
`trapped_chain_restart`; `Tuning()` and `Adaptation()`
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

## Which path to use (measured; `STUDIES/python_callpath_linux_v1`, WP78)

Every path runs the same kernel, so ESS per gradient is the same to
Monte-Carlo noise (paths that call the same compiled function give
bit-identical draws); what differs is the cost of one call. Measured on
Linux (four pinned cores of a shared 16-core box, CPython 3.12) on a 100-D
Gaussian, noncentered Eight Schools and a 157-D hierarchical regression,
4 chains x 1,000/1,000 at the defaults, against a native Rust target with
the same density:

| path | µs per gradient, `threads=1` (gauss / eight / hier) | vs native Rust | `threads=4` vs `threads=1` |
|---|---|---|---|
| native Rust `Target` | 1.6 / 0.6 / 3.8 | 1 | 3.4–3.8x faster |
| `from_cfunc` (numba `cfunc`) | 1.7 / 0.7 / 3.8 | 0.98–1.15x | 3.4–3.8x faster |
| `from_pymc(model, gil_free=True)` | 1.9 / 1.3 / 15 | 1.2–4.0x | 3.2–3.8x faster |
| plain callable calling a numba `njit` kernel | 3.1 / 2.0 / 5.3 | 1.4–3.5x | 0.39–0.82x (slower) |
| `from_pymc(model)` (default: PyTensor C function, a Python callable) | 6.7 / 10 / 34 | 4–17x | 0.45–0.80x (slower) |
| `from_jax(logp)` | 23 / 22 / 44 | 11–39x | 0.46–0.68x (slower) |

The Windows measurements (`STUDIES/python_callpath_v1`, WP47, contended)
rank the paths the same way.

Guidance:

* **PyMC models: use `from_pymc(model, gil_free=True)` with `threads=4`.**
  On Linux it gave 8–22x the ESS/s of the default `from_pymc(model)` at
  `threads=1`, with every gate passed. It needs numba. A model it cannot
  snapshot (for example `pm.Data` together with explicit `initval`s on
  PyMC >= 5.28) fails closed with `NotImplementedError`; the fallback is
  `from_pymc(model)` at `threads=1`.
* **nutpie on PyMC models.** nutpie 0.16.8 needs 1.4–1.9x fewer gradients
  per unit of ESS on these models (pooled 1.67x on Linux, 1.70x on
  Windows; adaptation, not the call path), so on smooth and larger
  hierarchical models (the Gaussian and the hierarchical regression) it is
  1.4–1.9x faster per second than `gil_free=True` at four cores. On
  noncentered Eight Schools nutpie fails the convergence gates on every
  seed (divergences), where every oWALNUTS path passes.
* **Hand-written densities: use `from_cfunc`**, with numba
  `error_model="numpy"` on the `cfunc` and its `njit` helpers and the
  nonfinite guard (return `-inf`, gradient zeroed, when the value or any
  gradient element is nonfinite; example below). It runs within 1.15x of a
  native Rust target and scales 3.4–3.8x on four threads. Numba's default
  `error_model="python"` raises `ZeroDivisionError` on a float division by
  zero, which cannot cross the C ABI: the call returns garbage and the run
  fails with "raw target wrote a nonfinite gradient element". The callable
  transport hides this (it treats `ZeroDivisionError` and any nonfinite
  output as a zero-density point by default).
* **Python callables (numpy, JAX, PyTorch, the default `from_pymc`): use
  `threads=1`.** A callable holds the GIL, so chains on worker threads queue
  for it; `threads=4` was slower than `threads=1` on every model.
  `from_pymc(model)` needs `thread_safe=True` for `threads > 1`.
* **`from_jax` adds about 20–40 µs per gradient** (JAX's per-call
  dispatch), which dominates small models: 0.09–0.14x the ESS/s of a
  compiled numba callable. Prefer a numba `cfunc` when the density is
  cheap.
* PyTorch's per-call cost is mostly autograd/dispatcher overhead; it is the
  slowest path for small models (WP47: 66–500 µs per call).

## Tests

```console
.venv\Scripts\python -m pytest -q
```

## GIL-free chains

Every `sample` call releases the GIL for the whole run; at `threads=1` the
chains run on the calling thread, at `threads > 1` on Rust worker threads.
A Python callable re-attaches the interpreter on each call, so those chains
are serialised by the GIL (use `threads=1`; see "Which path to use").
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
transforms or changed parameter layouts also fail before sampling. The
function is compiled with PyTensor's numba fastmath off, so draws are the
same whether the process compiled the model fresh or loaded it from numba's
file cache (WP86); they differ in the last bits from a `mode="NUMBA"`
callable, which keeps fastmath.
Nonfinite densities or gradients during proposals
become recoverable zero-density evaluations, matching the callable adapter's
default; an invalid initial point still fails verification.
On Linux (WP78) it ran at 1.2–4.0x a native Rust target's cost per gradient
and 8–22x the default `from_pymc(model)` ESS/s.
The callback must be thread-safe, deterministic, write every gradient
element on finite returns, and never raise across the ABI (hence
`error_model="numpy"` for numba).

## Warm continuation

`start_session` serves one fixed target of fixed dimension. When the target
changes (a new observation, a new latent coordinate), `sample_warm` refreshes
the posterior from a carried state instead of a refit (the WP84 warm path,
`STUDIES/online_sv_quote_v1`, as a library call since WP87): per chain its
last draw, its adapted step size and its adapted diagonal mass, run for
`draws` transitions with no warmup and no adaptation, each chain on its own
frozen step and metric. Chain `c` is bit-identical to the single-chain
`sample(target, dim, init=positions[c:c+1], chains=1, warmup=0, draws=k,
seed=seed + c, adaptation=None, mass=mass_diagonal[c],
tuning=replace(tuning, step_size=step_sizes[c]))`
(`tests/test_warm_continuation.py`). It does not re-adapt, it carries
diagonal metrics only (a structured-mass result raises), the fill of new
coordinates is yours to choose, and the library does not validate that `k`
draws reach any accuracy: in WP84, 50–200 draws per chain stayed calibrated
over 100 ticks (20–80 ms per tick on a 250-return SV model) but did not reach
the R-hat 1.01 / reference-MCSE bar. `ContinuationChunk.warm_state()` gives
the same state from a session.

```python
import numpy as np, owalnuts

def make_target(y):                       # dim = 1 + len(y): [mu, z_1..z_n]
    n = len(y)
    def logp_and_grad(q):
        mu, z = q[0], q[1:]
        lp = -0.5 * mu * mu - 0.5 * float(z @ z) - 0.5 * float(((y - mu - z) ** 2).sum())
        r = y - mu - z
        return lp, np.concatenate([[-mu + r.sum()], -z + r])
    return logp_and_grad

y = np.random.default_rng(0).normal(size=250)
result = owalnuts.sample(make_target(y), 1 + len(y), warmup=1000, draws=1000, seed=1)
state = result.warm_state()               # positions (4, 251), step_sizes (4,), mass_diagonal (4, 251)

for tick, y_new in enumerate(np.random.default_rng(1).normal(size=100)):
    y = np.append(y, y_new)
    state = state.extend_to(1 + len(y), position=0.0, mass=1.0)   # new latent: prior median, prior variance
    refreshed = owalnuts.sample_warm(make_target(y), state, draws=100, seed=1000 + tick)
    state = refreshed.warm_state()        # the next tick starts here
    quote = refreshed.samples[:, :, 0].mean()
```

For a loop of refreshes, `WarmSession` keeps the target, a pool of
`threads` workers and every per-chain input resident across calls (WP91):
`refresh(draws)` returns a `WarmChunk` (`samples` of shape `(chains,
draws, dim)`, per-chain `diagnostics` and `metadata`, the call's `seed`
and `target_calls`), `state()` is the current `WarmState`,
`retarget(target, state)` swaps both (a new dimension is allowed) and
`close()` joins (also on leaving a `with` block). Call `n` is bit-identical
to `sample_warm(target, state_n, draws=k, seed=seed + n * chains)` on the
state before the call (`tests/test_warm_session.py`). `WarmState.remap(dim,
map, fill)` rebuilds the state for a new coordinate layout and
`WarmState.shift_window(drop_front, append, position, mass)` is the
fixed-lag move: drop the oldest latents, append new ones at the prior fill.
In the Rust microbenchmark (`examples/warm_session_bench.rs`, one
contended laptop, 4 chains x 4 threads) the session saved about 0.3-0.5 ms
per call over `run_warm` (a 53-coordinate window: 0.37 ms versus 0.70 ms at
5 transitions per chain); the rest of a call is kernel work. The Python
transport adds its own per-call cost on top (array conversion, and the GIL
for callables).

```python
window = 50                                # fixed-lag window: [mu, z_1..z_50]
y = np.random.default_rng(0).normal(size=window)
result = owalnuts.sample(make_target(y), 1 + window, warmup=1000, draws=1000, seed=1)

with owalnuts.WarmSession(make_target(y), result.warm_state(), seed=1000, threads=4) as session:
    for y_new in np.random.default_rng(1).normal(size=20):
        y = np.append(y[1:], y_new)                                   # slide the data window
        state = session.state().remap(1 + window,                     # keep mu, drop z_1, shift, append z_new
                                      lambda j: 0 if j == 0 else (j + 1 if j < window else None),
                                      fill=(0.0, 1.0))
        session.retarget(make_target(y), state)
        chunk = session.refresh(50)                                   # 50 transitions per chain
        quote = chunk.samples[:, :, 0].mean()
```

(`shift_window(1, 1)` would also drop `mu`; the remap keeps coordinate 0
and slides the latents.)

When the tick needs a quote, not the draws, `refresh_functionals(draws,
functionals)` (WP95) evaluates functions of the position on every retained
draw inside the chain loop and returns a `FunctionalChunk`: `values` of
shape `(chains, draws, outputs)`, streamed per-chain `moments`, the
diagnostics, `positions` and `warm_state()`, but no draws
(`retain_draws=True` keeps them), with `mean(i)`, `variance(i)` and
`quantile(q, i)` pooled over every chain (or `per_chain=True`). A
functional is a numba `cfunc` with the signature
`numba_functional_signature()` (`void(intp dim, double* q, double* out,
intp n_out, void* user_data)`, GIL-free, evaluated on the worker threads),
or a Python callable `f(position) -> array` (its output count probed
once; the interpreter is attached once per draw per chain, which on the
SV targets of `bench/warm_functionals_bench.py` cost 0.16 ms (53
coordinates) to 0.55 ms (253 coordinates) per draw per chain, serialised,
most of it the callable's own numpy work, so use a `cfunc` on the tick
path). The values are the functionals of `refresh`'s draws bit for bit
and the draws do not depend on the functionals
(`tests/test_warm_functionals.py`). Per tick, a P95 of next-period
volatility on the fixed-lag window above:

```python
import numba

rho = 0.95

@numba.cfunc(owalnuts.numba_functional_signature(), nopython=True, error_model="numpy")
def sigma_next(dim, q_ptr, out, n_out, user_data):      # q = [mu, log sigma, beta, z_1..z_n]
    q = numba.carray(q_ptr, (dim,))
    mu, sigma = q[0], np.exp(q[1])
    h = mu + sigma / np.sqrt(1.0 - rho * rho) * q[3]
    for i in range(4, dim):
        h = mu + rho * (h - mu) + sigma * q[i]
    out[0] = np.exp((mu + rho * (h - mu)) / 2.0)         # exp(h_{n+1} / 2)

window = 50                                            # SV state: [mu, log sigma, beta, z_1..z_window]
dim = 3 + window
quote = [owalnuts.from_cfunc_functional(sigma_next, 1)]
with owalnuts.WarmSession(sv_target(y), state, seed=1000, threads=4) as session:
    for y_new in stream:
        y = np.append(y[1:], y_new)
        state = session.state().remap(dim, lambda j: j if j < 3 else (j + 1 if j < dim - 1 else None),
                                      fill=(0.0, 1.0))    # keep the three scales, slide the latents
        session.retarget(sv_target(y), state)
        chunk = session.refresh_functionals(50, quote)     # values (4, 50, 1); no draws kept
        sigma_p50, sigma_p95 = chunk.quantile([0.5, 0.95], 0)
```

(`sv_target` is the SV model as a `from_cfunc` target, as in
`bench/warm_functionals_bench.py`; `chunk.warm_state()` is the next state
when the draws are not kept.)

## Example: stochastic volatility on the top-5 cryptocurrencies

`examples/crypto_sv.ipynb` (executed notebook) and `examples/crypto_sv.py`
sample the full posterior of a standard SV model over up to 3,153 daily
returns of BTC/ETH/XRP/BNB/SOL through `from_pymc(model, gil_free=True)` with
a tridiagonal-precision path metric — seconds of wall time, zero divergences,
cross-checked against nutpie and NumPyro in the preregistered study
`STUDIES/flagship_crypto_sv_v1` (which also carries the honest limitations:
the shared global-ridge bottleneck and two backends' stuck seeds).
