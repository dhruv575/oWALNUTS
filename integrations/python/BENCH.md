# Python target overhead benchmark (preregistered)

Frozen before execution on 2026-08-31. Fresh seeds `93001`–`93003` (verified
absent from every ledger and study). Kernel v10 (`ALGORITHM_REVISION`
`…-v10`), `owalnuts` Python package `0.1.0b2`, Python 3.11.16, one machine
shared with other running agents (wall times carry that caveat; ESS per
target call is the machine-independent figure).

## Question

How much does routing a target through Python cost relative to a hand-written
Rust `Target`, per backend (numpy, JAX `jit(value_and_grad)`, PyTorch
autograd, PyMC compiled `logp_dlogp_function`), and can the Python package
beat NumPyro NUTS on NumPyro's own JAX log density?

## Targets and settings

1. **Noncentered Eight Schools** (v38 unconstrained coordinates
   `(mu, log tau, z_1..8)`; identical density in every backend up to an
   additive constant for PyMC). Four frozen starts `log tau ∈ {−2,−1,0,1}`,
   `mu = z = 0`. 1,000 warmup / 1,000 retained, four sequential chains,
   target acceptance .95, depth 8, initial step 0.3, `max_error` 1.0,
   8 refinement levels, diagonal mass adaptation. NumPyro: same starts,
   `target_accept_prob=.95`, `max_tree_depth=8`, diagonal adaptation, four
   sequential chains, 1,000/1,000.
2. **Gaussian local-level path with fixed globals** (WP4 target,
   `m0=0, tau0=1, mu=0.01, sigma_x=0.08`, `R_t = 0.0125(1+s_t²+1/(v_t+1))`),
   data simulated in numpy with seed `2026083131` and shared by every backend.
   `T ∈ {100, 1000}`. 500 warmup / 1,000 retained (T=1000) or 2,000 (T=100),
   four sequential chains, prior-drawn starts, target acceptance .8, depth 8,
   initial step 0.1, `max_error` 1.0, 3 refinement levels, mass adaptation
   off; arms **identity** metric and **posterior-precision tridiagonal**
   metric (`tridiagonal_precision_mass`). NumPyro: identity metric
   (`adapt_mass_matrix=False`), depth 8, same draws.

## Backends

`native` (Rust `Target` compiled into the extension, same code as the
studies), `numpy` (hand-written gradient), `jax` (`jit(value_and_grad)`,
x64), `torch` (autograd, float64, CPU), `pymc` (Eight Schools only,
`model.logp_dlogp_function(ravel_inputs=True)`), `numpyro` (NUTS on the JAX
log density; external reference; its `num_steps` is a leapfrog proxy for
work, labelled as such).

## Measurements

* per-call wall of each callable (median of 2,000 calls at the first start);
* sampling wall (warm: second run for JAX-based backends, first-run wall
  reported separately as "compile included");
* retained target calls (oWALNUTS exact fused calls; NumPyro `num_steps`
  proxy);
* ArviZ bulk ESS (minimum over the six Eight Schools functionals
  `mu, tau, mean(theta), sd(theta), theta_1, theta_8`; minimum over eight
  evenly spaced path coordinates plus the path mean for local level);
* ESS per retained call and ESS per second;
* fraction of sampling wall spent inside the Python callback (measured by the
  extension as time attached to the interpreter);
* posterior agreement: every backend's functional means within 3 MCSE of the
  native run on the same seed;
* GIL: Eight Schools numpy and native backends with `chains=4` at
  `threads=1` vs `threads=4`.

## Predictions (written before running)

1. Native and numpy/JAX/torch backends agree bitwise on target calls and
   samples for the same seed (the kernel is deterministic; the callback only
   changes timing) — provided the float64 gradients agree to ~1e-12, which
   JAX and torch should; numpy may differ at the last bit and then diverge
   after the first accept/reject decision that flips.
2. Per-call overhead: numpy ≈ 10–30 µs, JAX jit dispatch ≈ 50–150 µs,
   torch ≈ 100–300 µs, PyMC compiled ≈ 20–60 µs, native < 1 µs for Eight
   Schools.
3. oWALNUTS+JAX beats NumPyro NUTS on ESS/s on Eight Schools only if
   NumPyro's per-transition overhead exceeds oWALNUTS's per-call Python
   overhead × calls per transition (~15); expect roughly parity to 2×
   either way, not the 2.4× of the native track.
4. `threads=4` gives no speedup for Python backends (GIL serialises the
   target) and ~3–4× for native.

## Gates

Health: zero divergences, no `invalid_evaluation` stops, max-depth rate ≤1%,
R-hat ≤1.01 for every oWALNUTS cell; posterior agreement as above. Cells
failing health are reported, not dropped.
