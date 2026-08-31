# Preregistered canonical-v3 (scale-non-centered) study — WP17

Frozen before any sampling on 2026-08-31. Program:
`wiki/research-program-2026-08-31.md`. Motivation: WP4b
(`WP4B-REAL-TARGET-PATH-METRIC-V1`) found that `sspd-10` — the
`sigma_x -> 0` cell (truth `sigma_x = 1e-4`, posterior `sigma_x ≈ 1e-3`) — is
not sampled by any tested Euclidean sampler (NumPyro NUTS at depth 12:
1,510 divergences, R-hat 1.29; oWALNUTS I/P/B: R-hat 2.8–3.9, 33–74% depth
caps), and diagnosed that every centeredness `a` keeps the innovations in
absolute units, so all share the `sigma_x` funnel.

## Question

Does a scale-non-centered parameterization of the innovations remove the
funnel from the path coordinates, and once it does, does the within-orbit
refinement of oWALNUTS (JMLR Appendix C adaptation, 8 refinement levels)
earn its keep relative to plain dual averaging — measured, not asserted?

## canonical-v3 transform

canonical-v2 innovation coordinates: `q = [mu, log sigma_x, log alpha,
log beta, log gamma, log eta, x_1, d_2..d_T]` with `d_t = x_t - x_{t-1}
~ N(mu, sigma_x^2)`.

canonical-v3: `z = [same six globals, x_1, eps_2..eps_T]` with

    d_t = mu + sigma_x * eps_t,   eps_t ~ N(0, 1) a priori.

The map `z -> q` is block lower-triangular (globals unchanged, `x_1`
unchanged, `d_t` depends on `eps_t`, `mu`, `sigma_x`) with diagonal
`sigma_x` on the `T-1` innovation rows, so

    log p_z(z) = log p_q(q(z)) + (T - 1) * log sigma_x,

and the innovation prior in `z` reduces to a standard normal. Gradient by
the chain rule: `g_z[eps_t] = sigma_x g_q[d_t]`;
`g_z[mu] = g_q[mu] + sum_t g_q[d_t]`;
`g_z[log sigma_x] = g_q[log sigma_x] + sigma_x sum_t eps_t g_q[d_t] + (T - 1)`.
Location stays centered inside the affine innovation map; the observation
model, priors and globals are exactly canonical-v2.

Verification before sampling (unit tests in `src/v3.rs` / `src/main.rs`):
(i) `z -> q -> z` round trip; (ii) `lp_z = lp_q + (T-1) log sigma_x`;
(iii) gradient versus central finite differences at 20 random points
(tolerance `1e-6 |g| + 1e-5`, `eps = 1e-4`, on the T=48 parity data);
(iv) functionals agree between v2 and v3 coordinates of the same state;
(v) recoverable-error mapping. The sampling-level same-posterior check is
gate G7 below on `sspd-05`.

## Fixtures, seeds, starts

| id | fixture | SHA-256 | truth `sigma_x` | role | seed |
|---|---|---|---|---|---|
| sspd-10 | `sspd-10-n1000-strong-near_funnel_zero-…` | `005a5c7d…687ac` | 1e-4 | primary | 95001 |
| sspd-11 | `sspd-11-n1000-mixed-regular-…-cold` | `2fff9766…83baad` | 0.18 | non-regression | 95002 |
| sspd-05 | `sspd-05-n100-mixed-regular-…` | `1d10f68e…8091d` | 0.18 | non-regression, v2/v3 check | 95003 |

Seeds 95001–95003 verified absent from every ledger and study by grep.
Starts: WP4b rule (data-informed `initial_innovations`, `mu` offsets
`[-0.03, -0.01, 0.01, 0.03]`, zero `log sigma_x` offsets; sspd-11 cold
factor not applied), generated in innovation coordinates once and mapped
into v2 (`a = 1`) and v3 coordinates, so every arm starts from the same
physical states.

## Arms

All oWALNUTS arms: 4 chains, 4 threads, 500 discarded / 2,000 retained,
depth 8, identity initial diagonal, diagonal mass adaptation ON, zero-callback
preflight, 15-minute wall cap per arm (draws are not reduced; a cap hit is a
failure and is recorded).

* **V2-I** — control: canonical-v2 in `a = 1` coordinates; `KernelTuning
  (step 0.1, depth 8, min_micro 1, 3 levels, max_error 1.0)`, dual averaging
  at target acceptance 0.8 with initial step search. Identical to WP4b/WP12
  arm I.
* **V3-D** — canonical-v3, same tuning and adaptation as V2-I.
* **V3-A** — canonical-v3, JMLR Appendix C adaptation (`PaperAdaptationConfig
  (Delta 2, p_a .95, Gamma .8)`, v3 defaults: per-transition statistic,
  continue-through-δ-install), `KernelTuning(step 0.1, depth 8, min_micro 1,
  8 levels, initial max_error 1.0)`, no initial step search (as WP9). Runs
  through the budgeted facade with the exact worst-case admission and a
  200M runtime callback cap.
* **V2-A** — secondary: canonical-v2 `a = 1` with the V3-A adaptation.
  Tests whether refinement alone handles the centered funnel.
* **N3** — external reference on the v3 density: NumPyro 0.21 NUTS,
  `potential_fn` = −(v3 log density), 4 sequential chains, 1,000 warmup /
  2,000 retained, `target_accept 0.9`, `max_tree_depth 12`, adapted diagonal,
  same starts. JAX transcription parity-checked against the pinned
  canonical-v2 oracle (4/4 cases) plus a v2/v3 consistency check before
  sampling. 30-minute cap.

Arm order per fixture: V2-I, V3-D, V3-A, V2-A; fixtures sspd-10, sspd-11,
sspd-05. N3 runs independently.

## Functionals

`mu, sigma_x, alpha, beta, gamma, nu, x_terminal, x_path_mean`, computed
from the latent path in original units in every arm.

## Gates (per arm and fixture)

G1 rank-normalised folded split R-hat ≤ 1.01 on all eight functionals;
G2 bulk ESS ≥ 400 and G3 tail ESS ≥ 400 on all eight;
G4 zero retained divergences; G5 zero retained invalid evaluations;
G6 zero retained refinement exhaustions; G6b max-depth rate ≤ 1%
(NumPyro: depth-12 hits);
G7 posterior agreement: every functional mean within 3 combined MCSE of the
comparison arm (`sqrt(mcse_a² + mcse_b²)`, MCSE = sd/sqrt(bulk ESS)),
reported for V3-D vs V2-I, V3-A vs V3-D, V3-D vs N3, V3-A vs N3.
"Pass" = G1–G6b; agreement is reported alongside. Where an arm has
non-mixing chains, agreement is reported but not interpreted.

Refinement evidence (reported, not gated): per-arm retained max |ΔH|
quantiles, orbit energy-range quantiles, selected-refinement-level
histogram, retained unrefined-leaf fraction, final δ/h per chain, Appendix C
window telemetry, min bulk ESS per retained target call.

## Predictions (written before execution)

P1 sspd-10: V3-D max-depth rate ≤ 1% and R-hat/ESS gates pass on the six
globals; V2-I caps (> 10%) as in WP4b.
P2 sspd-10: V3-A ≥ V3-D on min bulk ESS per retained target call.
P3 sspd-10: N3 divergences < 151 (10% of WP4b's 1,510 at a = 1); pass/fail
not predicted.
P4 sspd-11: V3-D passes health (G4–G6b) but has lower min bulk ESS per call
than V2-I; V3 arms may fail G2/G3 (non-centering is wrong when the data are
informative about the path).
P5 sspd-05: V2-I and V3-D both pass G1–G6b and agree (G7).
P6 V2-A keeps V2-I's health status on every fixture; on sspd-10 it does not
remove the caps.

## Deviations

None planned. Any cap hit, rerun, or amendment is recorded here before the
next execution with a timestamp.

### Deviation 1 (2026-08-31, before any N3 result existed)

The first N3 launch used the system Python (ArviZ 1.3), whose `from_dict`
signature change crashed the script after `sspd-10` sampling but before any
result or diagnostic was written or observed. N3 was relaunched unchanged
under `C:\dev\polyscope\.venv-bench` (Python 3.11, jax 0.10.2, numpyro 0.21.0,
arviz 0.23.4). The same seeds are re-consumed; no analysis input existed from
the failed process, so no selection was possible.
