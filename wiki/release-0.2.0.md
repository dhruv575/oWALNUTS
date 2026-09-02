# Release 0.2.0 (2026-09-02)

First non-beta release of `owalnuts`. Kernel revision
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10` (unchanged since
0.1.0-beta.2; every pinned fingerprint and oracle still holds); paper
adaptation `walnutpie-paper-adaptation-kquantile-gamma-v4`; structured
refresh `walnutpie-structured-metric-refresh-v1`.

## What changed since 0.1.0-beta.2

| Merge | Change | Evidence |
|---|---|---|
| `0eafc49` | `owalnuts::diagnostics` (rank-normalised R-hat, bulk/tail/quantile ESS, MCSE, Stan-style `Summary`) and `owalnuts::export::CmdStanCsv` | ArviZ fixture `tests/data/arviz_fixture.json` (1e-6 relative); `tests/export_cmdstan.rs` |
| `00e55a7` | `owalnuts::sampler` builder API; `research` Cargo feature gate | `tests/sampler_api.rs` (bit-identical to the `walnutpie` entry points) |
| `97c593b` | Allocation-free kernel hot path, bit-identical | `tests/kernel_fingerprint.rs`; `examples/kernel_bench.rs` |
| `e79cb0f` | `owalnuts-autodiff` fused-primitive tape crate (`integrations/autodiff`) | `integrations/AUTODIFF-RESEARCH.md` Â§Route (e) |
| `52be19e` | posteriordb benchmark against CmdStan and nutpie | WP22-POSTERIORDB-BENCH-V1 |
| `be2325c` | BridgeStan: non-threaded build, `ReplicatedStanTarget`, NaN/inf mapped to the recoverable path | `STUDIES/posteriordb_bench_v1/artifacts/wall-gap` |
| `5417e0c` | `sampler::Init` uniform starts with retries; Appendix C v4 defaults and guards | `STUDIES/paper_adaptation_robust_v1` |
| `80403fc` | `sampler::Tuning` default depth 10; opt-in Stan-style warmup controls | `STUDIES/adaptation_parity_v1` |
| `c4a4086`, `54081e1` | Opt-in `KernelOptions` (`UTurnRule`, `ExhaustionRule`), `RunConfig::with_cached_initial_evaluation`; `Sampler` caches the initial evaluation by default (bit-identical draws, one call per transition saved) | `STUDIES/kernel_efficiency_v1` |
| this release | CHANGELOG, version 0.2.0, Python package 0.2.0 (`init="uniform"`, `summary()`, sampler defaults), CI for the integration crates | â€” |

The upgrade notes (facade unchanged, research items behind the feature,
sampler defaults `h = 0.5`, depth 10, `delta = 1` versus the frozen
`RunConfig`/`KernelTuning` defaults) are in `CHANGELOG.md`.

## Validation evidence

Every number is traceable to a preregistered, checksummed study under
`STUDIES/` (ledger entries in `research-ledger-2026-08-31.md`) or to a
committed benchmark in the tree.

### posteriordb against CmdStan and nutpie (WP22)

`STUDIES/posteriordb_bench_v1`: 17 posteriors, four arms (oWALNUTS dual
averaging, oWALNUTS Appendix C v3, CmdStan, nutpie), three seeds, gates
rank R-hat <= 1.01 and bulk/tail ESS >= 400. With the 0.1 defaults
(`h0 = 0.1`, depth 8):

| Measure | Result |
|---|---|
| Cells passing all gates | CmdStan 34/51, nutpie 29/51, oWALNUTS-DA 26/51, oWALNUTS-paper (v3) 8/51 |
| DA / CmdStan, geomean over 14 models | **0.32x** bulk ESS per gradient, 0.11x bulk ESS per second (0 wins) |
| DA / nutpie | 0.25x per gradient, 0.26x per second |
| Refinement | engaged on ~1 % of retained leaves; every healthy cell agrees with the posteriordb reference |
| Only model where oWALNUTS is ahead | `gp_pois_regr`, on gates (zero divergences where both NUTS implementations diverge) |

The ESS-per-second gap was traced to the `STAN_THREADS` BridgeStan build on
mingw-w64 (emulated TLS, 9-16x per gradient); rebuilt without it, `arK`
wall falls 10.5 s -> 1.5 s against CmdStan's 1.0 s with bit-identical
trajectories. The per-gradient gap motivated the three follow-up studies
below; the study also rejected the v3 paper adaptation as a default (froze
on nine models).

### posteriordb v2 on the 0.2.0 defaults (WP23)

`STUDIES/posteriordb_bench_v2`: the v1 protocol rerun with depth 10, `h0 =
0.5`, `Init::uniform()` start retries, the non-`STAN_THREADS` BridgeStan
build and Appendix C v4, plus a `WarmupConfig::stan_style(0.8)` arm; 17
posteriors x 5 arms x 3 fresh seeds, all 255 cells present. Ledger entry
`WP23-POSTERIORDB-BENCH-V2`.

| arm | cells passing | ESS/grad vs CmdStan | ESS/s vs CmdStan | wall/grad vs CmdStan | ESS/grad vs nutpie | ESS/s vs nutpie |
|---|---:|---:|---:|---:|---:|---:|
| owalnuts-da | **32**/51 | 0.233 (17 models) | 0.307 | **0.771** | 0.230 | **1.108** |
| owalnuts-paper (v4) | 29/51 | 0.232 | 0.305 | 0.771 | 0.229 | 1.104 |
| owalnuts-stan-style | 32/51 | 0.319 | 0.450 | 0.767 | 0.238 | 1.125 |
| cmdstan | 35/51 | 1 | 1 | 1 | — | — |
| nutpie | 27/51 | — | — | — | 1 | 1 |

Zero oWALNUTS cells were lost to a fatal NaN/inf evaluation or an
unevaluable start (v1: 12); the paper arm no longer freezes on the
regressions and is at parity with dual averaging (geomean 0.995); depth 10
takes `diamonds` from 0/3 to 3/3 and `earnings` from 0/3 to 2/3. The
per-gradient gap to CmdStan did not move: 0.233x over 17 models, 0.447x
over the 15 models where no oWALNUTS chain freezes (`arma11` 0/3 and
`lotka_volterra` 1/3 freeze from uniform starts where every leaf fails at
every refinement level, which NUTS's reject-and-shrink survives); on the
healthy models 0.4–0.9x. Predictions P3 (wall per gradient) and P5 (no
fatal losses) held; P1 missed by one cell (32 vs >= 33), P2 (>= 0.45x) and
P4 (no frozen paper cell) did not hold, so the breadth-throughput release
gate is not met.


### posteriordb v3: the WP24 warmup rule validated (WP25)

`STUDIES/posteriordb_bench_v3`: v2's protocol on fresh seeds 79101–79103
after `ExhaustionRule::AcceptUnlessDivergent` became the sampler's warmup
default (`STUDIES/freeze_mode_v1`, `WP24-FREEZE-MODE-V1`); 17 posteriors x
4 arms x 3 seeds, 204 cells. Ledger entry `WP25-POSTERIORDB-BENCH-V3`.

| arm | cells passing | ESS/grad vs CmdStan | ESS/s vs CmdStan | wall/grad vs CmdStan | ESS/grad vs nutpie | ESS/s vs nutpie |
|---|---:|---:|---:|---:|---:|---:|
| owalnuts-da | **35**/51 | 0.344 | 0.492 | **0.751** | 0.296 | **1.350** |
| owalnuts-stan-style | 29/51 | 0.346 | 0.462 | 0.792 | 0.308 | 1.309 |
| cmdstan | 37/51 | 1 | 1 | 1 | — | — |
| nutpie | 31/51 | — | — | — | 1 | 1 |

Zero frozen chains; `arma11` 0/3 -> 2/3 and `lotka_volterra` 1/3 -> 3/3.
The remaining misses are single stalled chains: an `arma11` seed that
escapes the pin and then crawls at `h ~ 1e-8`, `sblrc`'s step collapse
under dual averaging, and a `hmm_drive_0` chain in a second mode.

### Adaptation ablation (`STUDIES/adaptation_parity_v1`)

Nine posteriordb models, two seeds, round-2 cells over the four Stan warmup
differences and the tree depth.

| Configuration | geomean vs 0.1 defaults | geomean vs CmdStan | gates |
|---|---:|---:|---|
| depth 10 (the new `sampler` default) | **1.45x** | **0.49x** | **17/18** (0.1 defaults: 12/18) |
| full `stan_style` preset with the initial-phase `delta` | 2.04x | 0.68x | 14/18; loses 12-16 % on `kidiq`, `mesquite`, `garch11`, fails R-hat on `kidiq`, `earnings` |

Depth 8 capped 55-85 % of transitions on the correlated regressions
(`diamonds`, `earnings`, `sblrc`) and failed every gate there; depth 10
passes them and is identical to depth 8 on the models whose trees never
reached it. None of the four Stan warmup differences helps alone, so only
the depth changes by default and the preset stays opt-in
(`WarmupConfig::stan_style`, `Adaptation::Custom`).

### Appendix C robustness (`STUDIES/paper_adaptation_robust_v1`)

Seven posteriordb freeze models, eleven arms, two seeds. The freezes were
traced to leaf-less transitions producing no `h` statistic and then to the
`1e3` step band, not to the `delta` rule. The `zero-wide` arm
(`with_exhausted_transitions_as_zero(true)` and a `1e6` step band, now
`PaperAdaptationConfig::default()` = v4) is robust on all 14 cells and
0.90-1.35x dual averaging's minimum bulk ESS per gradient (geomean 1.04);
every other arm, including the plain v3 default (geomean 0.055), fails the
preregistered bar.

### Kernel and API parity

- `tests/sampler_api.rs`: every `Sampler::run` path produces bit-identical
  draws to the `walnutpie` entry point it wraps.
- `tests/kernel_fingerprint.rs`: the allocation-free kernel reproduces the
  pinned run fingerprints in debug and release. `examples/kernel_bench.rs`
  (single thread, best of 3) measures the kernel overhead per fused target
  call at funnel 480 -> 255 ns, Gaussian-100D 2,002 -> 936 ns, Eight
  Schools 889 -> 510 ns, with allocations per call 8.5 -> 0.19, 14 -> 0.56
  and 14.4 -> 1.27.
- Diagnostics: R-hat, ESS (bulk, tail, quantile, mean) and MCSE agree with
  ArviZ to 1e-6 relative on the committed fixture; `az.summary` over the
  exported CmdStan CSV agrees with the Rust `Summary`. The Python package's
  `summary()` is the same code and is tested against `az.rhat`/`az.ess`/
  `az.mcse` in `integrations/python/tests`.

### Kernel efficiency against reference NUTS (`STUDIES/kernel_efficiency_v1`)

Clean-room reference NUTS harness, ESS per gradient (seed medians):

| Arm | Eight Schools | 100-D Gaussian | 50-D correlated Gaussian |
|---|---:|---:|---:|
| reference NUTS | 1.00x | 1.00x | 1.00x |
| oWALNUTS default kernel | 0.81x | 0.75x | 1.03x |
| + initial-evaluation cache (now the `Sampler` default; draws bit-identical) | 0.91x | 0.81x | 1.06x |
| + `UTurnRule::MomentumSum` (opt-in) | 0.86x | 1.09x | 1.07x |

The cause of the gap is a wasted re-evaluation of the current state at the
start of every transition (one gradient per transition, 11 % at 8-9 leaves
per orbit; exact to cache) plus the endpoint U-turn rule, which stops 3.4
leaves later per orbit than Stan's momentum sum on the isotropic Gaussian
for no ESS gain (neutral within noise elsewhere). The exhaustion rule never
triggers on these targets; the funnel tail mass is preserved under every
option (`examples/funnel_kernel_options.rs`). The momentum-sum rule stays
opt-in until the posteriordb re-run gates it.

### Autodiff (`integrations/AUTODIFF-RESEARCH.md`)

`owalnuts-autodiff` (route (e), pure Rust, `#![forbid(unsafe_code)]`):
gradient cost relative to the hand-written gradient is 7.6x / 4.1x on the
fused Eight Schools form (206 ns), 13.7x on Neal's 10-D funnel (104 ns),
3.0x / 2.8x on the local level `lupdf` at T = 100 / 1,000 (435 ns /
3.93 Âµs) and 4.6-4.8x on the noncentered local level; gradients agree with
the hand oracles to 1e-14 or better. For comparison, BridgeStan's Stan Math
gradient is 6.7 Âµs on Eight Schools with `STAN_THREADS` (0.59 Âµs without)
and 38 Âµs at T = 1,000; the Enzyme route needs a from-source rustc and is
parked (`integrations/enzyme`). The Python GIL-free transport
(`from_cfunc`, `from_pymc(gil_free=True)`) reaches ~31,000 min-bulk ESS/s
on Eight Schools at four threads, parity with nutpie.

## Known limitations

- **ESS per gradient on easy posteriors is 0.7-0.8x CmdStan** at matched
  step, depth histogram and gradient count (eight schools, arK, garch11,
  mesquite in `adaptation_parity_v1`). `kernel_efficiency_v1` accounts for
  it: the default kernel is 0.75-0.81x reference NUTS on Gaussians and Eight
  Schools (1.03x on the correlated Gaussian) because of the wasted
  re-evaluation per transition (0.9x at depth 3, 0.97x at depth 5) and the
  endpoint U-turn rule (0.75x on the isotropic Gaussian, 1.0x on the
  correlated one), with refinement rejections at 0.85-0.95x where refinement
  engages. The cache is now the `Sampler` default; Stan's momentum-sum
  U-turn rule is opt-in (`KernelOptions`) until the posteriordb re-run.
- **Refinement rarely engages on posteriordb models**: ~1 % of retained
  leaves refine (99 % at level 0), so on those targets oWALNUTS is NUTS with
  a slightly shorter step paying the reverse-check cost; the wins measured
  so far come from the funnel-type targets of the 0.1 program.
- **Appendix C shares dual averaging's step collapse from bad starts** on
  some seeds: `kidiq` 77201, `sblrc` 77202 and both `earnings` seeds in
  `paper_adaptation_robust_v1` adapt one chain's step to 5e-4 - 7e-4 and
  spend the run at the depth cap (R-hat 1.6-1.8) under both v4 and dual
  averaging. `Init::uniform` start retries are new in this release and were
  not part of that study.
- The `stan_style` warmup preset is opt-in because it regresses four models
  and fails R-hat on two.
- Paper adaptation is supported by the diagonal and fixed-operator facades
  only; the Ïƒ_x -> 0 state-space funnel (`sspd-10`) is not sampled by any
  Euclidean sampler tested; there is no step-jitter option; seeds are not
  portable across kernel revisions; cancellation and deadlines are
  cooperative (all carried from 0.1.0-beta.2).
- The BridgeStan crate's sampling tests need a locally compiled model and
  skip in CI; only its pure-Rust nonfinite-mapping tests run there.
- The Python package is not published; `maturin develop` from the tree.

## Release checklist

- [x] `cargo fmt --check`, `cargo clippy --all-targets --all-features -D
      warnings`, `-D warnings` rustdoc (GNU 1.88)
- [x] `cargo test --release` without (189) and with (204) the `research`
      feature
- [x] `owalnuts-autodiff` (16 tests) and `owalnuts-bridgestan` (12 tests,
      model tests run locally) green, fmt and clippy clean
- [x] Python package rebuilt and its pytest suite green
- [x] `cargo package --allow-dirty` verify build
- [ ] `git tag v0.2.0` and `cargo publish` â€” left to the maintainer
- [x] WP23 posteriordb v2 numbers above
