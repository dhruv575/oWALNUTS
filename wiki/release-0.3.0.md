# Release 0.3.0 (record 2026-10-25)

Kernel revision `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`. It has
not changed since 0.2.0, and every pinned kernel fingerprint and oracle still
holds. The paper adaptation revision is still
`walnutpie-paper-adaptation-kquantile-gamma-v4` and the structured refresh
revision is still `walnutpie-structured-metric-refresh-v1`. Three
sampler-facade defaults changed: the start rule, the nonfinite-position
policy and the dense warmup. The retained kernel did not change.

**Publication status: published 2026-10-25.** Tag `v0.3.0` = `ab29f490` (the CI-green tree `c1829523` plus docs, a Python 3.10 test skip and an xfail for the PyMC initval limitation). CI run 40222309336 passed every job; wheels run 40225555199 built the sdist and five abi3 wheels (Linux x86_64/aarch64, macOS x86_64/arm64, Windows x86_64), ran the optional-backend suites on Python 3.10 and 3.13, and published `owalnuts 0.3.0` to PyPI by trusted publishing; `cargo publish` placed `owalnuts 0.3.0` on crates.io from the same tree. The integration crates (`owalnuts-bridgestan`, `owalnuts-autodiff`, `owalnuts-autodiff-tape`) remain unpublished path dependencies, as in 0.2.0.**

## What changed since 0.2.0

| Merge / commit | Change | Evidence |
|---|---|---|
| `41b475bb`, `d1fc2ab9` | **DEFAULT CHANGE:** `Init::default()` / `run_from_random_starts` = `Init::best_of(16)`. Also adds the opt-in `Init::Candidates`, `best_of(k)`, `median_of(k)`, `StartSelection` and `candidate_starts`, and `DEFAULT_INIT_CANDIDATES = 16` | `STUDIES/init_rule_v1` (WP43), `STUDIES/init_rule_confirmation_v1` (WP52) |
| `f097391c` | **DEFAULT CHANGE:** `sampler::Tuning::default()` uses `NonfinitePositionPolicy::RejectLeaf`, and the setter is out of `research`. `KernelTuning::default()` keeps `Abort` | `STUDIES/nonfinite_policy_requalification_v1` (WP54) |
| `b09035c4`, `59dec98c` | **DEFAULT CHANGE (engineering decision):** dense warmup uses `DenseWarmupSeeding::PerTransition`, `DenseMetricRegularization::Stan` and a symmetrised precision. Also fixes the `Metric::dense()` admission | `STUDIES/dense_metric_posteriordb_v1` (WP48), `STUDIES/dense_metric_confirmation_v1` (WP51, rule failed) |
| `b6035aae` | Observe-only `ChainWarning` / `Summary::chain_warnings` with end-of-warmup and retained-draw window telemetry | `STUDIES/chain_disagreement_warning_v1` (WP44) |
| `554abb08` | `ChainWarning::NonfinitePositions`: a per-chain line for rejected nonfinite positions | WP59; `tests/chain_warnings.rs` |
| `b1edc676` | Opt-in `DiagonalMetricRegularization::{ScaleFreeMedian, ScaleFreeStanMedian}` | `STUDIES/metric_regularisation_scalefree_v1` (WP41, not a default) |
| `457119f4` | `owalnuts-bridgestan`: opt-in Windows concurrent replicas for static-runtime DLLs; `tools/build_static_runtime.py`; direct replicas zero the gradient buffer | `STUDIES/bridgestan_windows_root_cause_v1`–`v5` (WP50–WP50E) |
| `329f12e1`, `465616bf` | Python: one thread state per worker, `from_jax` without `jnp.asarray`, and a `from_pymc(gil_free=True)` import fix for PyMC 5.28+ | `STUDIES/python_callpath_v1` (WP47) |
| `7a634a13` | **Python DEFAULT CHANGE:** `sample(init=None)` = Rust `Init::best_of(16)`. Adds `init="best_of"` / `"jitter"` and `best_of_starts` | `STUDIES/nutpie_per_gradient_gap_v1` (WP58 follow-up) |
| `50953f52` | Research-only `WarmupConfig::with_initial_phase_max_depth` (default `None`) | `STUDIES/lotka_volterra_stall_v1` (WP57) |

Full entries are in `CHANGELOG.md`.

## Validation evidence

Every number below is from a preregistered, checksummed study under
`STUDIES/`. Walls are contended and are not evidence unless stated.

### posteriordb v7 and its seed extension (WP56, WP62)

`STUDIES/posteriordb_bench_v7` ran the 0.3.0 defaults (`f097391c`) on the
v6 protocol, plus five hard posteriors from WP46. The arms were oWALNUTS at
the `Sampler::new()` defaults, CmdStan 2.39.0 and nutpie 0.16.8, 4 x
1,000/1,000, seeds 560561–560563.

| Measure | oWALNUTS | CmdStan | nutpie |
|---|---|---|---|
| House cells passing (17 posteriors) | **43/51** | 34/51 | 26/51 |
| Five hard posteriors | 6/15 | 7/15 | 3/15 |
| ESS/gradient vs CmdStan, fixed 15 complete | 0.708 | — | — |
| Largest passing reference \|z\| | 3.82 | | |
| Funnel z (3 seeds) | +1.69, -0.59, +0.84 | | |

All 66 oWALNUTS cells completed, with no error, timeout or frozen chain. The
v6 release rule was **not met**. Its per-gradient clause (>= 0.75) was
unevaluable and below threshold, and wall per gradient was 1.85x CmdStan
through the Windows owned worker. On the hard five, oWALNUTS passed
kilpisjarvi and grsm 3/3 and failed GLMM_Poisson, `seeds_centered` and
centred radon 0/3. On `seeds_centered`, CmdStan and nutpie also recorded
zero divergences.

Paired attribution put best-of-16 starts at 1.061x uniform (WP60) and
reinstalled chain rescue at 1.023x (WP61), so neither explains the v6 -> v7
drop (0.848 -> 0.708). `STUDIES/posteriordb_bench_v7_seed_extension` (WP62)
added three seeds. The geomean is **0.810** on the new seeds and **0.761 over
six seeds**, with a leave-one-seed-out interval of [0.740, 0.822]. Gates
pooled over six seeds were 80/96 for oWALNUTS against 62/96 for CmdStan. No
passing oWALNUTS cell has |z| > 4. A ±0.05 per-gradient gate would need about
49 seeds, so the release gates are the pass counts and z.

### Neal's funnel over 30 seeds (WP53)

`STUDIES/funnel_defaults_30seed_v1` ran the defaults at 4 x 2,000/20,000 on
30 seeds. 4/30 seeds have |z| > 2 (all low), with mean z -0.419 and sd 1.13.
The preregistered failure rule R1 (> 20 % exceedance or |mean z| > 0.5) did
not fire. The four bad cells had at most one divergence each, no
`chain_warnings` and R-hat <= 1.008. Pooled P(omega < -5) is
0.0458 ± 0.0014 against the exact 0.0478, a 4–5 % deficit that `delta = 2`
shares (0.0455). `delta = 2` had 0/30 exceedances and 37 divergences against
the default's 43. Rule R2 recommends it for a posteriordb confirmation; no
default changed. At the house budget (1,000/1,000), no arm passes the health
gates on the funnel.

### Default-flip confirmations (WP52, WP54)

- **Best-of-16 starts (WP52).** On fresh seeds 952201–952203 the frozen rule
  passed: 1.254x geomean min-bulk-ESS per gradient over 17 models, 42 vs 42
  gates, funnel |z| <= 1.11, and no hide event on a 0.7/0.3 two-Gaussian
  target. The gain is `arma11` (59.8x) and `lotka_volterra` (17.1x); the
  other 14 models are 0.862x.
- **`RejectLeaf` (WP54).** Draws were bit-identical on 73/73 cells that
  `Abort` completed, and 75 vs 73 runs completed. The WP50D/E fatal sblrc
  seed 50801734 now passes every gate (max |z| 1.63). The funnel passes. The
  benefit rests on that one non-fresh seed.

### Dense facade (WP48, WP51)

The old `Metric::dense()` warmup was 0.055x the diagonal per gradient, with
12/51 gates. The fixed warmup is 3.21x, with 40/51 gates against the
diagonal's 43/51 (`diamonds` 98.7x; `gp_pois_regr` 3/3 -> 0/3). WP51's
frozen rule compared the fixed warmup with the diagonal and failed. The
default change is an engineering decision on new-versus-old dense evidence.
Dense is never selected automatically. In v7's descriptive dense arm it
passed 18/18 on six correlated regressions, at 13.4x the diagonal
(`diamonds` 67.5x).

### Python package (WP47, WP58)

- WP47: Python callables at threads=4 are 1.1–1.9x faster, and `from_jax`
  is 2.0–2.6x ESS/s. Draws are bit-identical. `from_pymc(thread_safe=True)`
  at threads=4 no longer recompiles per callback.
- WP58: `init=None` drew unchecked starts and failed all 12 Python
  `lotka_volterra` runs at transition 0. It is now the Rust best-of-16 rule,
  and a test checks that it is bit-identical to `run_from_random_starts`.

### Windows BridgeStan static runtime (WP50–WP50E)

- **WP50C, static mingw runtime:** 0/360 faults against 2/120 for dynamic
  DLLs, and 3.2x (sblrc) / 4.0x (arK) contended sampling wall with
  bit-identical draws.
- **WP50D, confirmatory gate:** not supported. Static DLLs failed 1/1000,
  with a sampler nonfinite-position error and not a crash, against 4/300
  crashes for dynamic DLLs.
- **WP50E:** replayed that seed 6/6 as a deterministic integrator overflow.

The concurrent dispatch ships opt-in, and the owned worker stays the
default.

## Known limitations

- **`accel_gp`:** 0/3 and 0.35x CmdStan per gradient in v7. That figure is
  stable over six seeds (WP62), and a dense metric does not rescue it
  (WP51).
- **Funnel tail deficit:** at the defaults, pooled P(omega < -5) is 4–5 %
  low over 30 seeds. 4/30 seeds fall below z = -2 with no diagnostic
  signal. Its source (step or metric adaptation, not `delta`) is open
  (WP53).
- **`hmm_drive_0` second modes under best-of-16:** a chain was held about
  62 nats down in a second mode on 2 of 5 fresh seeds. Gates were 15/30
  against uniform's 18/30 on six suspect models (WP60). `chain_warnings`
  named the chain in both cells, so check it as well as R-hat.
- **`lotka_volterra` trapped chains:** there are no stalls at the defaults
  (0/12, against 4/4 with uniform starts). One chain is trapped in a
  secondary mode on 2 of 12 seeds (R-hat 1.59). Neither `best_of(64)` nor
  an initial-phase depth cap fixes it (WP57).
- **nutpie's per-gradient lead on smooth PyMC models:** about 1.70x pooled
  over the three WP47 models (WP58). It comes from warmup spend (44 % of the
  gap) and nutpie's gradient-based mass matrix (44–60 %), not from WALNUTS
  refinement (5–7 %). On eight schools, eight_nc and `gp_pois_regr`, nutpie
  fails the gates where oWALNUTS passes.
- **`from_pymc(gil_free=True)` and initial values:** the GIL-free snapshot
  needs constant initial values. A model whose initial point fails
  verification, or one that freezing would change, is rejected before
  sampling. Use `gil_free=False` for those models
  (`integrations/python/README.md`).
- Unchanged from 0.2.0: the Windows default is one effective BridgeStan
  replica per target, and the centred Eight Schools fails every sampler.

## Upgrading from 0.2.0

The kernel, `ALGORITHM_REVISION` and the kernel fingerprints are unchanged.
Runs configured through `RunConfig` / `KernelTuning` are unaffected. Each
default change can be reverted:

| Default change | Restore the 0.2.0 behaviour |
|---|---|
| Start rule `Init::best_of(16)` (`Init::default()`, `run_from_random_starts`): draws for a given seed differ | `sampler.run_with_init(&target, &Init::uniform())`, or explicit starts with `.run(&target, &starts)` |
| `NonfinitePositionPolicy::RejectLeaf`: an overflow becomes a rejected leaf, with no divergence | `.tuning(Tuning::default().nonfinite_position(NonfinitePositionPolicy::Abort))` |
| Dense warmup `PerTransition` / `Stan` / symmetrised: dense runs from earlier builds do not reproduce | on the `WarmupConfig` passed through `Adaptation::Custom`: `.with_dense_warmup_seeding(DenseWarmupSeeding::Legacy).with_dense_metric_regularization(DenseMetricRegularization::MeanVarianceShrinkage).with_dense_symmetrized_precision(false)` |
| Python `sample(init=None)` = best-of-16 | `init="jitter"`, which reproduces old `init=None` runs bit for bit; `init="uniform"` and explicit arrays are unchanged |

`Summary` may now print `warning: chain k ...` lines. They are observe-only
and never change a draw.
