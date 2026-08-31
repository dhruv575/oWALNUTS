# Release 0.1.0-beta.2 (2026-08-31)

First release candidate of `owalnuts`. Kernel revision
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`; paper adaptation
`walnutpie-paper-adaptation-kquantile-gamma-v3`.

## What changed since the checkpoint (`d900c9c`)

| Commit | Change | Evidence |
|---|---|---|
| `556cc15`, `5dd3716` | JMLR Appendix C adaptation (`PaperAdaptationConfig`) | WP1 milestone in `sampler-path-ledger.md` |
| `29621b8`, `1666dbb` | Kernel `v9`: endpoint-error micro acceptance (reference parity; funnel bias removed) | WP6-FUNNEL-BIAS-FIX-V9 |
| `cfd813b`, `8cadd94` | Paper-mode `v2` statistic/bound and `v3` continue-through-δ default | WP9-PAPER-H-RULE-STABILISATION-V2 |
| `452befb` | Kernel `v10`: recoverable failures refine like upstream | WP10-INVALID-EVALUATION-PARITY-V10 |
| this release | CHANGELOG, README, examples, CI, package metadata | — |

## Validation evidence

Every number is traceable to a preregistered, checksummed study under
`STUDIES/` and its ledger entry in `research-ledger-2026-08-31.md`.

| Target | Result | Entry |
|---|---|---|
| Neal's funnel, paper tuning, 4×50k | P(ω<−5) 0.0474 vs exact 0.0478; var 9.04; 0 div/invalid/exhaust; reference gives 0.0477 | WP6-FUNNEL-BIAS-FIX-V9 |
| Neal's funnel, Appendix C warmup from δ=1, h=0.1 | unbiased; step spread ≤1.27×; 1.41×/1.61× ESS/call vs fixed paper tuning | WP9-PAPER-H-RULE-STABILISATION-V2 |
| Eight Schools (v38 strict track), kernel v9 | 12,830 bulk / 10,346 tail ESS/s conservative minimum, 7 seeds; ≥2× every strict competitor; ESS/call unchanged vs v7 | WP8-EIGHT-SCHOOLS-V9-REBENCH-V1 |
| Eight Schools outer-selection ablation | biased progressive (default) 1.75× ESS/call over exact multinomial | WP3-1 |
| Exact Gaussian state space, T=100/1000 | posterior-precision path metric: depth 3–4, MC-accurate; prior-based metric caps 92% | WP4-ESSGT-V1 |
| Polyscope canonical-v2, T=1000 (sspd-11) | adapted diagonal passes where NumPyro passes, confirmed 3/3 fresh seeds; path block 2.7× ESS/call, 2/3 under the strict gate (not confirmed) | WP4B-REAL-TARGET-PATH-METRIC-V1, WP12-SSPD11-CONFIRMATION-V1 |
| Polyscope canonical-v2, T=1000 (sspd-10, σ_x→0 funnel) | no tested Euclidean sampler passes, NumPyro included | WP4B-REAL-TARGET-PATH-METRIC-V1 |
| Stock–Watson SV (simulated) | adaptation arm passes all gates on 2/3 fresh seeds at 4×2,000, 2.0× ESS/call vs fixed paper tuning; paper's energy-error contrast is data-specific | WP2b-SW-REPRO-V1, WP12-SSPD11-CONFIRMATION-V1 |
| Recoverable-failure semantics | 4,000/4,000 oracle leaves; 0 invalid stops across 216k transitions; truncated Gaussian stationary | WP10-INVALID-EVALUATION-PARITY-V10 |

## Erratum

The Eight Schools figures previously circulated (19,054.65 / 14,494.34 ESS/s)
were the minimum over functionals of the across-seed median, not a true
minimum; the like-for-like v7 minimum was 8,634 / 5,949 ESS/s. The qualitative
claim ("fastest among strict matched competitors tested locally") holds under
both the corrected v7 minimum and the v9 re-measurement. See
`STUDIES/eight_schools_v9_rebench_v1/RELEASE-NOTE.md`.

## Known limitations

- Paper adaptation is supported by the diagonal and fixed-operator facades
  only; dense-adaptive, projected and pooled facades reject it.
- The σ_x → 0 funnel cell of the state-space family (`sspd-10`) is not
  sampled by any Euclidean sampler tested; it needs a reparameterisation, not
  a metric.
- Stock–Watson evidence is simulated data; 2/3 fresh seeds pass the strict
  R-hat gate at 4×2,000 draws.
- On an exactly whitened Gaussian a fixed macro step can alias the
  tree-doubling schedule (see `examples/state_space_path_metric.rs`); there is
  no step jitter option yet.
- Seeds are not portable across kernel revisions.
- Cancellation and deadlines are cooperative.

## Release checklist

- [x] `cargo test` (GNU 1.88), strict Clippy, `fmt --check`, `-D warnings`
      rustdoc
- [x] `cargo package --locked` verify build
- [x] Examples build and run
- [ ] `git tag v0.1.0-beta.2` and `cargo publish` — left to the maintainer
