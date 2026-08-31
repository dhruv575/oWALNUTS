# Preregistered real-target path-metric study (WP4b)

Frozen before any sampling on 2026-08-31. Program:
`wiki/research-program-2026-08-31.md`; motivation: WP4 (`WP4-ESSGT-V1`).

## Question

Does WP4's finding transfer to the real `polyscope-canonical-v2` target at
T=1000: in centered (a=1) coordinates, does a fixed posterior-precision
tridiagonal path metric mix at shallow depth, does the plain adapted diagonal
in centered coordinates stay off the depth cap, and does the production
a=0.75 diagonal baseline cap as rows 72/77 of the Polyscope ledger report?
And, for the first time, what does an external NUTS reference do on the same
fixtures?

## Target and fixtures

`polyscope-canonical-v2` (Student-t observations, six globals, `T+6`
unconstrained coordinates), ported verbatim from
`POLYSCOPE_WEB/processor/owalnuts_local/src/canonical.rs` with the
triangular unit-Jacobian centeredness map generalised to `a ∈ {0.75, 1}`.
Parity against `fixtures/polyscope_parity.json` (SHA-256
`4c91f5fd…8ac0f0c`) is a unit test that must pass before sampling, in Rust
and in JAX.

| id | fixture | SHA-256 | role |
|---|---|---|---|
| sspd-11 | `sspd-11-n1000-mixed-regular-moderate-h1-none-none-cold.json` | `2fff9766…83baad` | primary T=1000, non-pathological |
| sspd-10 | `sspd-10-n1000-strong-near_funnel_zero-moderate-h1-blocks-contaminated-regular.json` | `005a5c7d…687ac` | secondary T=1000, pathological |
| sspd-05 | `sspd-05-n100-mixed-regular-moderate-h0-blocks-contaminated-regular.json` | `1d10f68e…8091d` | T=100 sanity |

Deviation, declared: the sspd-11 fixture's `initialization.kind = "cold"`
(+6 on every innovation coordinate) is **not** applied. All fixtures use the
regular start rule of prior studies — `initial_params` (data-informed
innovations) plus `mu` offsets `[-0.03, -0.01, 0.01, 0.03]` and zero
`log sigma_x` offsets — so that the study isolates posterior geometry and
metric from start recovery. Starts are generated once
(`make_starts.py`) in innovation coordinates, shared by every arm, and the
Rust runner verifies them against its own computation.

## Seeds

Fresh: sspd-11 → 86001, sspd-10 → 86002, sspd-05 → 86003 (verified absent
from every ledger and study by word-boundary grep). oWALNUTS chain `i` uses
`splitmix64(seed + i)`; NumPyro uses `PRNGKey(seed)`.

## Arms

**N — external reference (run first, independent of the Rust kernel).**
NumPyro 0.21 NUTS, `potential_fn` on the same density in y-coordinates,
4 sequential chains, 1,000 warmup / 2,000 retained, `target_accept_prob 0.9`,
`max_tree_depth 12`, adapted diagonal metric (`dense_mass=False`), identical
starts. Executed for a=1 on all fixtures, then a=0.75 on all fixtures; a
30-minute cap per run is recorded as a deviation if hit.

**oWALNUTS arms** — a=1 unless stated; globals free; 4 chains, 500 discarded
/ 2,000 retained; `KernelTuning(step 0.1, depth 8, min_micro 1, refinement
levels 3, max_error 1.0)`; `WarmupConfig(0.8)` with initial step search and
dual-averaged step; zero-callback preflight; per-arm 15-minute cap.

* **I** — `sample_chains`, identity initial `DiagonalMass`, diagonal mass
  adaptation ON (the centered-coordinate analogue of default diagonal NUTS
  adaptation).
* **P** — `sample_chains_structured`, mass adaptation OFF (the structured
  facade does not adapt), `StructuredBlockMass([globals, path])`:
  globals block = `BidiagonalCholesky` with zero subdiagonal and diagonal
  `sqrt(m_g)` where `m_g` is the geometric mean over chains of arm I's
  adapted momentum-covariance diagonal for the six globals (recorded in
  `artifacts/.../<fixture>-globals-mass.json`); path block =
  `BidiagonalCholesky` = Cholesky factor of the tridiagonal precision
  `H = [1/tau² at x_1] + Q_rw(sigma_x) + diag(c_t)` computed ONCE at the
  data-informed globals of `initial_params` (`sigma_x` from the innovation
  variance, `alpha = gamma = residual sd`, `beta = e^{-2}`, `nu = 3`), with
  `c_t = (nu+1)/(nu · (alpha² + beta² s_t² + gamma²/(v_t+1)))` the Student-t
  curvature at zero residual.
* **B** — production baseline: a=0.75 coordinates, `sample_chains`, identity
  initial diagonal, mass adaptation ON. Same tuning as I. Expected to
  reproduce Polyscope rows 72/77 (depth caps); draws are capped only if the
  15-minute cap is hit, and that is recorded.

Arms run in the order I, P, B per fixture; fixtures in the order sspd-11,
sspd-10, sspd-05.

## Functionals

`mu, sigma_x, alpha, beta, gamma, nu, x_terminal, x_path_mean` (eight),
computed identically in Rust and JAX from the latent path.

## Gates (reported per arm and fixture; pass/fail)

* rank-normalised folded split R-hat ≤ 1.01 on all eight functionals;
* bulk ESS ≥ 400 and tail ESS ≥ 400 on all eight;
* zero retained divergences, invalid evaluations, refinement exhaustions;
* maximum-depth stop rate ≤ 1% (oWALNUTS: `StopReason::MaximumDepth` at
  depth 8; NumPyro: tree depth 12 hits);
* posterior agreement, arm P versus arm N (a=1): every functional mean within
  3 combined MCSE (`sqrt(mcse_P² + mcse_N²)`, MCSE = sd/sqrt(bulk ESS)).
  Arm N is the reference; disagreement is charged to oWALNUTS.

## Predictions (written before execution)

1. sspd-11: P passes all gates with median depth ≤ 5.
2. sspd-11: I passes, or fails only ESS gates narrowly, and does not cap
   (max-depth rate ≤ 1%).
3. sspd-11: B caps (max-depth rate > 1%, expected ≫ 10%) and fails R-hat/ESS.
4. sspd-10: no prediction for pass/fail; report N versus I/P/B. If N fails
   too, the fixture, not the sampler, is implicated.
5. sspd-05: all oWALNUTS arms and N pass (sanity).

## Provenance recorded per Rust artifact

`owalnuts::walnutpie::ALGORITHM_REVISION`, kernel git commit, fixture
SHA-256, seed, preflight worst-case/admission ceiling/callbacks started
(must be 0), wall, target calls. A kernel change (WP6) during the run is
expected; oWALNUTS arms are re-runnable with `--arms I,P,B --out
artifacts/owalnuts-v<k>` without touching `artifacts/numpyro`.
