# Release 0.2.0 (unpublished; record updated 2026-09-04)

First non-beta release of `owalnuts`. Kernel revision
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10` (unchanged since
0.1.0-beta.2; every pinned fingerprint and oracle still holds); paper
adaptation `walnutpie-paper-adaptation-kquantile-gamma-v4`; structured
refresh `walnutpie-structured-metric-refresh-v1`.

**Publication status (updated 2026-09-04): blocked.** WP36 resolves the
default-safety decision: the 0.2 sampler default is **no chain rescue**, while
explicit rescue policies remain available. The separate Windows BridgeStan
process-lifecycle failure has a narrow mitigation: one owned worker per target
plus process-global native-call serialization completed a final 720-child
Windows GNU diagnostic without a fault. The historical root cause is not
proven. CI now defines Windows MSVC core/integration and Windows MSVC plus
Linux real-model BridgeStan gates, and the release workflow defines the full
package/wheel matrix, but those external runs remain pending. Do not tag or
publish until those release gates are green.

## What changed since 0.1.0-beta.2

| Merge | Change | Evidence |
|---|---|---|
| `0eafc49` | `owalnuts::diagnostics` (rank-normalised R-hat, bulk/tail/quantile ESS, MCSE, Stan-style `Summary`) and `owalnuts::export::CmdStanCsv` | ArviZ fixture `tests/data/arviz_fixture.json` (1e-6 relative); `tests/export_cmdstan.rs` |
| `00e55a7` | `owalnuts::sampler` builder API; `research` Cargo feature gate | `tests/sampler_api.rs` (bit-identical to the `walnutpie` entry points) |
| `97c593b` | Allocation-free kernel hot path, bit-identical | `tests/kernel_fingerprint.rs`; `examples/kernel_bench.rs` |
| `e79cb0f` | `owalnuts-autodiff` fused-primitive tape crate (`integrations/autodiff`) | `integrations/AUTODIFF-RESEARCH.md` § Route (e) |
| `52be19e` | posteriordb benchmark against CmdStan and nutpie | WP22-POSTERIORDB-BENCH-V1 |
| `be2325c` | BridgeStan: non-threaded build, `ReplicatedStanTarget`, NaN/inf mapped to the recoverable path | `STUDIES/posteriordb_bench_v1/artifacts/wall-gap` |
| `5417e0c` | `sampler::Init` uniform starts with retries; Appendix C v4 defaults and guards | `STUDIES/paper_adaptation_robust_v1` |
| `80403fc` | `sampler::Tuning` default depth 10; opt-in Stan-style warmup controls | `STUDIES/adaptation_parity_v1` |
| `c4a4086`, `54081e1` | Opt-in `KernelOptions` (`UTurnRule`, `ExhaustionRule`), `RunConfig::with_cached_initial_evaluation`; `Sampler` caches the initial evaluation by default (bit-identical draws, one call per transition saved) | `STUDIES/kernel_efficiency_v1` |
| this release | `sampler::Tuning` default refinement levels 4 -> 8: the four-level default halved the funnel's tail mass; eight levels are exact on three seeds at 1.05x / 1.00x ESS per call on Eight Schools and a 100-D Gaussian | `STUDIES/funnel_defaults_v1` (WP28) |
| this release | **DEFAULT CHANGE (post-hoc after WP31)**: `sampler::Tuning::default()` U-turn rule `Endpoints` -> `MomentumSum`; `Adaptation::DualAveraging` / `Paper` regularise the diagonal metric with Stan's prior (`DEFAULT_U_TURN_RULE`, `DEFAULT_METRIC_REGULARIZATION`) | `STUDIES/joint_default_v1` (WP31, rule not met, decided post hoc), validated by `STUDIES/posteriordb_bench_v5` (WP32) |
| `87d8817` | **FINAL DEFAULT CHANGE (WP36):** `sampler::DEFAULT_CHAIN_RESCUE = None`; default output is directly tested against explicit custom no-rescue warmup, while observe-only, `restart_from_best`, `two_hit` and pooling remain explicit policies | `STUDIES/chain_rescue_v2` (WP36) |
| this release | Windows BridgeStan: one owned OS worker per target, one effective replica regardless of the requested count, and process-global native-call serialization; requested/effective replica and execution metadata are public | `STUDIES/bridgestan_lifetime_v1` (rejected first mitigation), `STUDIES/bridgestan_owned_worker_v1` (accepted narrow final qualification) |
| this release | CHANGELOG, version 0.2.0, Python package 0.2.0 (`init="uniform"`, `summary()`, sampler defaults), CI for the integration crates | — |

The upgrade notes (facade unchanged, research items behind the feature,
sampler defaults `h = 0.5`, depth 10, eight levels, `delta = 1` versus the frozen
`RunConfig`/`KernelTuning` defaults, and no automatic chain rescue) are in
`CHANGELOG.md`.

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

### The sampler defaults on Neal's funnel (WP28)

`STUDIES/funnel_defaults_v1`, preregistered, seeds 82101-82103, 10-D funnel
4 x 2,000 / 20,000 at the sampler defaults plus one override per arm, with
the noncentered Eight Schools and a 100-D Gaussian as cost cells:

| arm | P(omega<-5) per seed (z), exact 0.0478 | retained div / exhaust | funnel calls | Eight Schools ESS/call | Gaussian ESS/call |
|---|---|---|---|---|---|
| four levels (0.2.0 before this change) | 0.0203 (-3.5), 0.0242 (-3.8), 0.0625 (+0.3) | 54 / 2,933 | 1.00x | 1.00x | 1.00x |
| **eight levels (the default)** | 0.0412 (-0.3), 0.0346 (-1.4), 0.0897 (+1.0) | 8 / 113 | 1.08x | 1.05x | 1.00x |
| eight levels + `delta = 0.5` | 0.0376 (-1.9), 0.0397 (-0.8), 0.0413 (-0.7) | 0 / 157 | 0.74x | 0.91x | 0.79x |
| `delta = 0.5` alone | 0.0403, 0.0126 (-6.0), 0.0206 (-3.5) | 268 / 11,416 | 0.61x | 0.91x | 0.78x |
| `Adaptation::Paper`, eight levels, from `h0 = 0.5` | 0.0432, 0.0459, 0.0293 (-2.7) | 0 / 4 | 0.68x | 1.09x | 0.39x |
| `stan_style(0.8)` | 0.0255 (-3.7), 0.0182 (-7.4), cell errored | 2,134 / 9,039 | 0.55x | 0.94x | 0.62x |
| one level (NUTS-like control) | 0.0058 (-11.8), 0, 0 | 5 / 78,469 | 0.41x | 1.15x | 1.05x |

The preregistered rule (cheapest arm within |z| <= 2 on every seed and
>= 0.9x on both cost targets) selects eight levels. What it does not fix:
one chain per seed still adapts to `h ~ 0.01` on the funnel and the `omega`
R-hat is 1.01-1.04 at 80,000 draws, so the default is unbiased there, not
efficient; the same step-collapse mode as `sblrc` / `earnings` in WP25.

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
| + `UTurnRule::MomentumSum` (then opt-in; now the sampler default) | 0.86x | 1.09x | 1.07x |

The cause of the gap is a wasted re-evaluation of the current state at the
start of every transition (one gradient per transition, 11 % at 8-9 leaves
per orbit; exact to cache) plus the endpoint U-turn rule, which stops 3.4
leaves later per orbit than Stan's momentum sum on the isotropic Gaussian
for no ESS gain (neutral within noise elsewhere). The exhaustion rule never
triggers on these targets; the funnel tail mass is preserved under every
option (`examples/funnel_kernel_options.rs`). WP26 initially kept the
momentum-sum rule opt-in; WP31 later made it the sampler default only in
combination with Stan metric regularisation, and WP32 validated that pair.

### U-turn rule default decision (WP26)

`STUDIES/uturn_default_v1`: the v3 protocol on fresh seeds 80101–80103 with
the U-turn rule as the only difference between arms (`Endpoints`,
`MomentumSum`, `EndpointsWithCross`; CmdStan cited from v3), plus the
funnel tail mass at the paper tuning and at the sampler defaults (three
seeds pooled) and the Eight Schools strict track. Rule: flip iff geomean
>= 1.10, no model < 0.85, funnel |z| <= 2 under both tunings, Eight Schools
>= 0.9. Result: `MomentumSum` / `Endpoints` = **1.064** geomean (kidiq 1.37,
garch 1.27, nes 1.18, one_comp 1.38, hmm_drive_0 1.26, lotka_volterra 2.14;
centered eight schools 0.78, diamonds 0.80, gp_pois_regr 0.85, noncentered
eight schools 0.88, arma11 0.90, arK 0.91, earnings 0.93), 37 vs 38 cells,
Eight Schools 1.08x, funnel at the paper tuning z +1.03 (endpoints +0.90),
funnel at the sampler defaults z −3.4 against the endpoint control's −11.2
— biased under every rule there. **Not flipped.** The endpoint arm
reproduces v3 (38/51, 0.434x CmdStan on these seeds; `hmm_drive_0` drew no
second-mode chain, `lotka_volterra` one `rk45`-boundary start). Ledger entry
`WP26-UTURN-DEFAULT-V1`.

### Joint default decision: `MomentumSum` + Stan's regularisation (WP31)

`STUDIES/joint_default_v1`: after `step_collapse_v1` (WP27: the default
metric regularisation floors small posterior variances at 0.01, Stan's
fixes `sblrc` but loses `earnings`) and `kernel_gap_v1` (WP30: at the
corrected metric the endpoint U-turn rule ends orbits at 0.6x NUTS's
length, `MomentumSum` restores them), the v3 protocol on fresh seeds
86101–86103 with four arms: the defaults, `MomentumSum` alone, Stan's
regularisation alone, and both (`joint`). Rule: flip iff `joint` >= 1.15x
geomean, no model < 0.85x, gates >= the default's, funnel |z| <= 2 on
every seed at both tunings, Eight Schools >= 0.9x. Result: `joint` /
default = **1.508** geomean (earnings 3.69, sblrc 9.12, arma11 2.26,
one_comp 2.16, kidiq 1.98, hmm_example 1.87, nes2000 1.50, garch 1.16,
mesquite 1.12, arK 1.07; diamonds 0.94, gp_pois_regr 0.98; centered eight
schools 0.79 and `hmm_drive_0` 0.005 — the two cells no arm passes),
**41 vs 35 cells**, funnel exact at both tunings with zero divergences
at the sampler defaults, Eight Schools 1.29x; 0.477x CmdStan against
the default's 0.317x, 0.81–0.99x on the healthy regressions. Either
option alone is not it: `MomentumSum` alone 1.12x, the regularisation
alone 1.26x but 0.08x and 0/3 on `earnings` (the short endpoint-rule
orbits leave the window variance at the prior's 1e-5 floor and the metric
overshoots 100x). **Not flipped by the study** — the preregistered
per-model floor failed on the mode lottery and the fail-everywhere cell.
**Flipped afterwards as a post-hoc decision**: the two C2 failures are
cells no arm passes, the other four criteria held with margin, and the
pair became `Tuning::default()` / `Adaptation::{DualAveraging, Paper}`
behaviour in the commit labelled "DEFAULT CHANGE (post-hoc after WP31)",
validated on fresh seeds against CmdStan and nutpie in
`STUDIES/posteriordb_bench_v5` (WP32, below). Ledger entry
`WP31-JOINT-DEFAULT-V1`.

### posteriordb v5: the 0.2.0 defaults as shipped, against CmdStan and nutpie (WP32)

`STUDIES/posteriordb_bench_v5`: the v3 protocol on the post-hoc defaults
(`MomentumSum` + Stan's regularisation), fresh seeds 87101–87103, CmdStan
2.39.0 and nutpie 0.16.8 rerun on the same seeds, predictions fixed before
the first cell (>= 39/51 gates, >= 0.45x CmdStan per gradient over 17,
>= 1.5x nutpie ESS/s, <= 1.0x CmdStan wall per gradient, funnel |z| <= 2 on
every seed at the defaults) — all five held. Ledger entry
`WP32-POSTERIORDB-BENCH-V5`. **This is the breadth figure for 0.2.0;** the
v3 table above is the pre-change history.

| arm | cells passing | models 3/3 | ESS/grad vs CmdStan | ESS/s vs CmdStan | wall/grad vs CmdStan | ESS/grad vs nutpie | ESS/s vs nutpie |
|---|---:|---:|---:|---:|---:|---:|---:|
| owalnuts-da (0.2.0 defaults) | **42**/51 | **12** | **1.069** over 17; **0.822** over the 16 without `arma11` | 1.401 | **0.801** | 0.841 (16) | **3.085** |
| cmdstan | 36/51 | 10 | 1 | 1 | 1 | — | — |
| nutpie | 28/51 | 8 | — | — | — | 1 | 1 |

Read the per-gradient figure as 0.82x: the 1.07x over all 17 is `arma11`,
where CmdStan and nutpie each lose two of three seeds to a chain that never
leaves its start (WP27's crawl start) and oWALNUTS passes 3/3 at 71x.
On the healthy regressions oWALNUTS is 0.67x (`earnings`), 0.92x
(`kidiq`), 0.87x (`sblrc`), 0.85x (`nes2000`), 0.90x (`mesquite`) of
CmdStan per gradient, against 0.22 / 0.47 / 0.09 / 0.58 / 0.88 in v3; the
DA arm's v5/v3 geomean is 2.01x per gradient at 1.02x the gradients, no
model below 0.8x. Outright wins (gates >=, more ESS per gradient and per
second): vs CmdStan `arma11` and the centered eight schools; vs nutpie
`diamonds`, `arma11`, `gp_pois_regr`. Gate wins: noncentered eight schools
(3/3; nutpie 0/3), `gp_pois_regr` (3/3; CmdStan 0/3 with 6–22
divergences, nutpie 0/3), `sblrc` (3/3; CmdStan 2/3). Still failing
everywhere: the centered eight schools, `accel_gp`. Funnel at the
defaults 0.0571 / 0.0474 / 0.0578 (z +1.02 / −0.05 / +0.93) with zero
divergences, one chain on one seed at `h` 0.0013 (unbiased, not efficient;
WP28). No oWALNUTS cell errored, froze or diverged.

### Autodiff (`integrations/AUTODIFF-RESEARCH.md`)

`owalnuts-autodiff` (route (e), pure Rust, `#![forbid(unsafe_code)]`):
gradient cost relative to the hand-written gradient is 7.6x / 4.1x on the
fused Eight Schools form (206 ns), 13.7x on Neal's 10-D funnel (104 ns),
3.0x / 2.8x on the local level `lupdf` at T = 100 / 1,000 (435 ns /
3.93 µs) and 4.6-4.8x on the noncentered local level; gradients agree with
the hand oracles to 1e-14 or better. For comparison, BridgeStan's Stan Math
gradient is 6.7 µs on Eight Schools with `STAN_THREADS` (0.59 µs without)
and 38 µs at T = 1,000; the Enzyme route needs a from-source rustc and is
parked (`integrations/enzyme`). The Python GIL-free transport
(`from_cfunc`, `from_pymc(gil_free=True)`) reaches ~31,000 min-bulk ESS/s
on Eight Schools at four threads, parity with nutpie.

## Known limitations

- **ESS per gradient on easy posteriors is 0.7-0.8x CmdStan** at matched
  step, depth histogram and gradient count (eight schools, arK, garch11,
  mesquite in `adaptation_parity_v1`). `kernel_efficiency_v1` accounts for
  it: the then-default endpoint-rule kernel was 0.75-0.81x reference NUTS on
  Gaussians and Eight Schools (1.03x on the correlated Gaussian) because of
  the wasted re-evaluation per transition (0.9x at depth 3, 0.97x at depth 5)
  and the endpoint U-turn rule (0.75x on the isotropic Gaussian, 1.0x on the
  correlated one), with refinement rejections at 0.85-0.95x where refinement
  engages. The cache and `UTurnRule::MomentumSum` are now `Sampler` defaults
  after the joint WP31 change and WP32 validation. Historically, WP26 tested
  `MomentumSum` in isolation: it was 1.064x geomean and 0.78–2.14x per model
  but missed that study's flip rule, so it correctly remained opt-in at that
  point. `UTurnRule::Endpoints` is now the explicit opt-in alternative and the
  frozen `walnutpie::KernelOptions::default()` behavior.
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
  only; the σ_x -> 0 state-space funnel (`sspd-10`) is not sampled by any
  Euclidean sampler tested; there is no step-jitter option; seeds are not
  portable across kernel revisions; cancellation and deadlines are
  cooperative (all carried from 0.1.0-beta.2).
- **Windows BridgeStan support is narrowly mitigated, not generally
  qualified.** WP35A and WP36 reproduced faults in the optional native
  replicated-target path. `bridgestan_lifetime_v1` then rejected resident
  DLLs plus scoped pools because the fixed arm still faulted in 8/180
  children. `bridgestan_owned_worker_v1` moved all native operations to one
  owned worker per target and serialized them process-wide; the final
  fixed-only matrix completed 540 ordinary plus 180 concurrent-target
  children with zero faults or correlated Event 1000 records (0/720,
  one-sided 95% upper bound 0.415210%) and exact counters/settings. Sampling
  was 3.1–5.1x the four-replica comparator. Root cause is still not proven,
  and qualification covers only Windows GNU, one host, three model binaries,
  short runs, and one effective replica per target. Windows MSVC,
  Linux/macOS and package/wheel gates remain pending. Windows Python
  `from_stan` and direct Python BridgeStan operations are disabled for 0.2.
  None of this identifies a defect in the core Rust sampler, whose direct
  tests and fingerprints remain green.
- CI now has a dedicated required-real-model job that compiles Eight Schools
  with BridgeStan 2.9.0 and runs the Rust BridgeStan tests on Linux GNU and a
  Windows MSVC Rust host loading a MinGW-built model. Its first external run
  is pending; the ordinary integration matrix still permits model-dependent
  tests to skip.
- The Python package is not published; `maturin develop` from the tree.

## Release checklist

- [x] `cargo fmt --check`, `cargo clippy --all-targets --all-features -D
      warnings`, `-D warnings` rustdoc (GNU 1.88)
- [x] `cargo test --release` without (218) and with (234) the `research`
      feature
- [x] `owalnuts-autodiff` (16 tests) and `owalnuts-bridgestan` (12 tests,
      model tests run locally) green, fmt and clippy clean
- [x] Python package rebuilt and its pytest suite green
- [x] `cargo package --allow-dirty` verify build
- [x] WP36 default-safety decision applied: no rescue by default; explicit
      policies remain available; default/no-rescue parity is tested
- [x] Replace the unsafe Windows replicated-target execution policy with the
      owned-one-worker/process-global-serialization backend and complete the
      final 720-child Windows GNU diagnostic; immutable earlier evidence was
      not rerun
- [ ] Observe a green dedicated BridgeStan 2.9.0 real-model CI gate on Linux
      GNU and on a Windows MSVC Rust host loading the MinGW-built model; the
      workflow is configured, but has not run externally. Windows Python
      `from_stan` remains disabled
- [ ] Observe green core and integration matrices including Windows MSVC 1.88,
      and green release jobs for Windows, manylinux x86_64/aarch64, macOS
      x86_64/arm64 and the sdist; these workflow gates are configured but
      remain pending
- [ ] Configure the repository `pypi` environment and pending PyPI trusted
      publisher, then push and observe the required CI gates
- [ ] `git tag v0.2.0`, `cargo publish` and PyPI publish — blocked on the
      preceding external gates

### Final default and benchmark status

The admitted release headline remains **WP32/posteriordb v5: 42/51 gates**.
Its no-rescue multi-chain warmup again matches the current sampler behavior
after the final WP36 default commit `87d8817`.

- **WP35 `posteriordb_bench_v6`** measured the temporary WP33
  `restart_from_best` default on fresh seeds: **45/51** gates against CmdStan
  34 and nutpie 29, no frozen chain, and funnel tail-mass |z| <= 2 on every
  seed. It did **not** meet its
  preregistered release rule: one passing `one_comp` cell has max |z| 4.023,
  and one `sblrc` oWALNUTS subprocess exited without a result, leaving the
  fixed-16 efficiency gates unevaluable (observed 0.848x CmdStan per gradient
  and 0.825x wall per gradient over the 15 complete models). The v5 table
  remains the last headline admitted by its own rule; WP35 must be reported
  beside it as historical evidence, not substituted silently.
- **WP35A `sblrc_process_stability_v1`** used 46 diagnostic-only children and
  reproduced one silent four-replica `0xC0000374` fault after durable result
  publication at `drop/before`; 45 children succeeded. Root cause is not
  established, and evidence seed 90101 was neither rerun nor used.
- **WP36 `chain_rescue_v2`** completed 288 launches: 281 process-valid, six
  heap-corruption exits, one post-result timeout and six invalid triplets.
  `two_hit` reduced nuisance unique-chain actions 35→14, but had only nine
  complete blocks and failed its registered efficacy, funnel, origin and
  efficiency gates. The registered fallback then found mapped-origin overwrite
  red lines in four `current` cells (five events) and selected `no_rescue`.
  The frozen classifier found pathological/frozen ARMA and Lotka-Volterra
  origins and zero HMM origins, so the study does **not** prove genuine
  posterior-mode destruction.
- **`bridgestan_lifetime_v1`** tested resident DLLs plus joined Rayon pools.
  Its fixed arm still faulted in **8/180** children, so that mitigation was
  rejected and remains recorded.
- **`bridgestan_owned_worker_v1`** replaced the Windows path with one owned
  worker per target and process-global serialization. The final matrix
  completed **720/720** children (540 ordinary, 180 concurrent four-target)
  with zero faults, exact parity/counters/settings, and one effective replica;
  the combined one-sided 95% upper bound is **0.415210%**. This clears only the
  recorded Windows GNU diagnostic gate. Root cause is not established and the
  broader release gates above remain.

No posteriordb v7 is required before release. This is a reasoned update to the
earlier plan, not result-driven benchmark substitution: the final sampler
restores v5's no-rescue defaults, and parity with explicit no rescue is tested
directly. A future v7 is required if an automatic cross-chain action is
reintroduced.

Post-release kernel research has not changed the candidate release:
WP37A did not qualify fixed `delta = 2` for its adaptive-to-2 path, and WP37B
is paused off-main after 73 of 84 launches because the first incumbent
state-space cell returned a fatal nonfinite target evaluation. Eleven WP37B
cells were never launched, its candidate is not qualified, and no default or
release number changed.

See [`research-program-2026-09-04.md`](research-program-2026-09-04.md) for the
full state and the open lines.
