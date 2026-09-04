# Research program 2026-09-04: the 0.2 program — make it usable, then make it competitive

Status: **resumed on 2026-09-04 for WP35; the run is complete and no sampling
is running.** Everything described here is merged into `main` at `0.2.0`;
nothing is pushed, tagged or published. Companion documents:
`research-program-2026-08-31.md`
(the programme that produced `0.1.0-beta.2`), `research-ledger-2026-08-31.md`
(one checksummed entry per study, WP22–WP35), `release-0.2.0.md`.

## What this programme was

The `0.1.0-beta.2` release had a rigorous kernel with leaf-for-leaf oracle
parity and a narrow evidence base: three target families, hand-written
gradients, one strict-matched throughput win. An external review on 2026-09-01
identified the adoption blockers as (1) a 107-item public surface with 35
`sample_*` entry points, (2) no gradient story for Rust users, (3) evidence
concentrated on targets chosen because the kernel was good at them, and (4) a
README written as a citation log. The coordinator approved a seven-item
programme: a small API, a posteriordb benchmark, a decision on making the JMLR
Appendix C adaptation the default, a Rust autodiff crate, kernel performance
work, diagnostics and export, and a README rewrite.

Items 1, 4, 5, 6 and 7 were engineering and are done. Item 2 turned out to be
the programme: the benchmark falsified far more than it confirmed, and every
subsequent study (WP24–WP34) exists because of something it found. Item 3 was
answered **no** by its own evidence.

## What shipped

**A small API.** `owalnuts::sampler` is 21 public items: one `Sampler` builder,
one `Posterior`, and `Metric` / `Adaptation` / `Tuning` / `Limits` / `Init`.
Every path is a thin wrapper over one `walnutpie` entry point and is tested to
produce bit-identical draws to calling that facade directly. The research-only
facades (projected and pooled arrowhead, the `direct_original_q` family, the
research evaluation limit) moved behind a `research` Cargo feature, off by
default. `walnutpie` remains public and frozen; `ALGORITHM_REVISION` never
changed during this programme.

**Diagnostics and export in the crate.** `owalnuts::diagnostics` computes
rank-normalised folded split R-hat, bulk, tail, quantile and mean ESS, MCSE and
type-7 quantiles, matching ArviZ to 1e-6 relative on a committed fixture, plus
per-chain sampler health and a `ChainDisagreement` report.
`owalnuts::export::CmdStanCsv` writes CmdStan-format CSV that
`arviz.from_cmdstan` reads, verified end to end against the Rust summary. No new
dependencies.

**A kernel that does not allocate.** Per-transition workspaces, in-place
gradient writes, an `Rc<State>` ring reused across leaves, and one redundant
re-validation removed took allocations per target call from 8.5–14.4 down to
0.19–1.27, and kernel overhead per call from 480 / 2002 / 889 ns to
131 / 557 / 320 ns on the funnel, a 100-D Gaussian and Eight Schools. Every
retained draw is bit-identical, pinned by `tests/kernel_fingerprint.rs`;
optimisations that would have changed floating-point operation order were
measured and rejected.

**Autodiff for Rust users.** `integrations/autodiff` is a fused-primitive arena
tape (`Var` handles, enum nodes, segmented n-ary nodes, `cumsum` blocks) at 2.8x
a hand-written gradient on a T=1000 state-space path, 4.1x on Eight Schools, and
13.7x on the 10-D funnel where the hand gradient is a 7.6 ns loop. For
comparison, BridgeStan is 6.7–38 µs per call and the `reverse` crate measured
58–68x.

**A Python package that cannot drift.** `integrations/python` now constructs
`owalnuts::sampler` types, so it inherits every default automatically, and a
test asserts its draws are bit-identical to a Rust `Sampler` run. It exposes
`owalnuts.DEFAULTS`, `init="uniform"`, `summary()`, `from_stan()` (BridgeStan
with GIL-free replicas) and the numba `cfunc` path. A `wheels.yml` matrix builds
abi3 wheels for Linux x86_64 and aarch64, macOS x86_64 and arm64, and Windows,
with an sdist that vendors the path-dependency crates and PyPI trusted
publishing gated on a tag. The name `owalnuts` is available on PyPI. The
non-Windows legs have not been exercised.

## The defaults changed eight times, each behind evidence

`walnutpie::RunConfig`, `WarmupConfig` and `KernelTuning` defaults are frozen for
the oracles; every change below is in `owalnuts::sampler` only.

| change | study | why |
|---|---|---|
| max depth 8 → 10 | `adaptation_parity_v1` | 1.45x ESS per gradient, 17/18 gates; fixed `diamonds` and `earnings` |
| cache the initial evaluation | WP30 `kernel_efficiency_v1` | the driver re-evaluated the current state every transition; draws bit-identical |
| admit the exact worst case | usability | the sampler's own defaults were rejected by the conservative preflight ceiling |
| Appendix C v4 robust rule | `paper_adaptation_robust_v1` | the K-quantile rule installed `delta ≈ 0` from bad starts and froze 9 of 17 models |
| `ExhaustionRule::AcceptUnlessDivergent` in warmup | WP24 `freeze_mode_v1` | the two-sided energy test killed the leaf Stan rides downhill; 12 of 12 `arma11` chains unfroze |
| refinement levels 4 → 8 | WP28 `funnel_defaults_v1` | four levels halved the funnel's tail mass at the adapted step; eight are exact and never engage elsewhere |
| `UTurnRule::MomentumSum` + `DiagonalMetricRegularization::Stan` | WP31 `joint_default_v1`, validated by WP32 | 1.508x ESS per gradient, 41/51 gates; neither works alone |
| chain rescue `restart_from_best` | WP33 `chain_rescue_v1` | 25 of 27 cells against the plain driver's 21; `lotka_volterra` 0/3 → 3/3 |

## What the benchmark did to us

Six posteriordb runs, each preregistered with fresh grep-verified seeds, 17
posteriors, 4 chains, 1,000 warmup and 1,000 retained, defaults on every sampler.

| run | ledger | oWALNUTS gates /51 | CmdStan | nutpie | ESS/gradient vs CmdStan | wall/gradient |
|---|---|---:|---:|---:|---|---|
| v1 | WP22 | 26 | 34 | 29 | 0.32x | about 10x slower |
| v2 | WP23 | 32 | 35 | 27 | 0.233x | 0.771x |
| v3 | WP25 | 35 | 37 | 31 | 0.344x | 0.751x |
| v4 | WP29 | partial, superseded | | | | |
| v5 | WP32 | **42** | 36 | 28 | 1.069x all / **0.822x** healthy | **0.80x** |
| v6 | WP35 | **45** | 34 | 29 | 0.848x on 15/16 fixed non-`arma11` models; one `sblrc` error | **0.825x** on those 15 |

v6 is the full-current-default run after WP33. It has the strongest gate count
but did **not** meet its preregistered release rule: a passing `one_comp` cell
has max |z| 4.023 and one `sblrc` oWALNUTS subprocess exited without a result,
so the fixed-16 efficiency criteria are unevaluable. v5 remains the last
headline admitted by its own rule; v6 must be reported beside it.

v1 was the falsification that mattered: at defaults the sampler lost to CmdStan
on every model, ran ten times slower per gradient, and the Appendix C adaptation
froze chains on nine of seventeen posteriors. Every number in the
`0.1.0-beta.2` README was true and none of it generalised.

The ten-times wall gap was not the sampler at all. Mingw-w64 GCC emulates
thread-local storage, and Stan Math touches its thread-local autodiff stack for
every node it records, so the `STAN_THREADS=true` BridgeStan build cost 10x per
call. A non-threaded build plus `ReplicatedStanTarget` (one loaded module per
thread, each with its own global stack) took `arK` from 10.54 s to 1.53 s at
identical trajectories. nutpie pays the same cost and cannot avoid it from this
repository.

## What we learned about the kernel

**The per-gradient gap decomposes cleanly.** Under CmdStan's own adapted step
and metric, against a clean-room reference NUTS, the default kernel was 0.77x on
ESS per gradient, and the factor is entirely **leaves per orbit** (0.60x).
Gradients per leaf is 1.01, and selection is exact: the biased-progressive joins
are already Stan's pair, and the selected-state displacement matches. Switching
to Stan's momentum-sum U-turn statistic restores 0.90x, and a
NUTS-inside-oWALNUTS control reaches 0.95x.

**Two half-fixes that only work together.** The unit-variance metric floor
installed a metric about 1000x too wide on `sblrc`, whose coefficients have
posterior variance 1e-5, so dual averaging correctly held the step at 0.003.
Stan's regularisation fixes that but *loses* gates, because short endpoint-rule
orbits at the corrected metric let a warmup window see no movement and re-floor
the variance. The momentum-sum rule's longer orbits let the window measure it.
Jointly: 1.508x, 41 of 51 gates, `sblrc` 0/3 → 3/3 at 9.12x. This is the
programme's central mechanical result.

**Freezes were a rule mismatch, not a bug.** From uniform(−2, 2) starts on
`arma11` the log density is −4.5e19 to −1.8e115; the step collapses until
`q + h·v == q`, and the kernel sits in a stable dual-averaging equilibrium with
no position change. CmdStan escapes because its divergence test is one-sided: at
`h ≈ 1e-28` the leapfrog drifts downhill with an astronomically *negative*
energy error, which Stan keeps with weight 1 and which WALNUTS's two-sided
`|H_end − H_start| ≤ delta` turns into an exhaustion at the initial leaf.

**Refinement does not pay on ordinary posteriors (WP34).** The adapted macro
step already equals Stan's step (geometric mean ratio 1.000 over 17 models),
refinement engages on 0.22% of leaves, and the level-0 leaf-error distribution is
one smooth population (q99/q50 about 10 everywhere) with no stiff subpopulation
for refinement to absorb. Raising the step moves the whole distribution —
`P(|dH| > 1)` goes from 0.4–6% at `h` to 28–62% at 2h — and every step-raising
arm loses per gradient. Where oWALNUTS is furthest behind CmdStan (`accel_gp`
0.47x, `gp_pois_regr` 0.75x, both eight schools), the cause is refinement's own
reverse-coarsening stop, which ends 10–54% of transitions there against 0.8–7%
on the regressions.

The honest conclusion is a statement about the target class. **WALNUTS wins
where stiffness is localised** — Neal's funnel, the T=1000 state-space path,
`gp_pois_regr` and the centered eight schools, where the NUTS implementations
diverge and it does not — **and reduces to NUTS with overhead where stiffness is
uniform.** The v5 gate lead is a robustness lead, not a per-gradient lead:
oWALNUTS finishes cleanly where CmdStan and nutpie leave a chain stuck or
divergent, while still spending more gradients per effective sample on healthy
models (0.67–0.95x).

## Open lines after WP35

1. **Chain-rescue safety and timing.** WP35 records 30 restarts in 21 cells:
   21 log-density and nine step events, including one log-density restart on
   every `hmm_drive_0` seed and two step restarts as late as transition 249.
   The next decision study should pair the current rule with a second-window
   or two-consecutive-boundary score and a no-rescue control. It must gate
   reference agreement and make the original mode assignment visible.
2. **The unexplained `sblrc` process exit.** Seed 90101 exited without stderr
   or raw JSON while 90102/90103 passed. Diagnose library load/unload and
   process stability with synthetic or non-evidence seeds before another
   breadth run; do not post-hoc rerun the WP35 cell.
3. **`delta = 2`, the strongest unexploited efficiency lead.** WP34's near-miss arm is
   1.070x over 17 models and 1.077x on the healthy ones at the *same* step and
   the same 42 gates, taking the CmdStan ratio from 0.850x to 0.915x;
   `da06-d2` reaches 1.122x on the healthy models. Both fail the preregistered
   no-model-below-0.85x clause only on `accel_gp` (0.68x and 0.22x), the model
   whose 54% reverse-coarsening rate means refinement is doing real work there.
   The right experiment is `delta` adapted per target from the observed `|dH|`
   distribution rather than a fixed constant, with the funnel and Eight Schools
   side checks that WP34 did not get to run.
4. **A cheaper reverse-coarsening check.** This is now the named residual on the
   hard models: WP30 measured it at 3–7% of orbits on regressions and WP34 at
   10–54% on the four worst models, and it is the difference between 0.90x and
   0.95x of reference NUTS.
5. **The funnel at the sampler defaults is unbiased but not efficient.** Eight
   levels fixed the tail mass (v5 per-seed z of +1.02, −0.05, +0.93), but one
   chain per seed still adapts to `h` between 0.001 and 0.02 and contributes
   almost no ESS. Eight levels with `delta = 0.5` mixes far better at a 21% cost
   on a 100-D Gaussian and remains a documented opt-in. WP35 again has exact
   per-seed tail mass, but omega bulk ESS 388/539/356 and two divergences on
   seed 90103.
6. **Targets nothing samples.** The centered eight schools and `accel_gp` fail
   almost every gate for every sampler (`accel_gp` is oWALNUTS 1/3 in WP35),
   and `hmm_drive_0` remains a start-draw mode question even though density
   rescue makes it 3/3 by moving the outlying chain. These belong in a
   known-hard list rather than in an ordinary tuning loop.
7. **Publishing.** crates.io and PyPI are both untouched. The wheel matrix has
   only been exercised on Windows; the manylinux and macOS legs, the MSVC
   toolchain and the Linux backends job are unverified.

## Method notes worth keeping

- Every study was preregistered with a frozen `protocol.json` and fresh
  grep-verified seeds before the first cell, and several were decided *against*
  the hypothesis that motivated them (WP26, WP27's default, WP29's stanreg arm,
  WP34). Two preregistered decision rules were met and applied (WP31 and WP32 as
  a labelled post-hoc flip, and WP33); the rest left the defaults alone.
- Bit-identity was the safety rail throughout. `tests/kernel_fingerprint.rs`
  pins the `walnutpie` defaults, and every performance or refactoring change had
  to reproduce it; two changes (WP30's cache, WP33's driver refactor) were
  accepted specifically because they were bit-identical.
- Wall times were measured on a shared machine with other agents running, so ESS
  per gradient is the machine-independent figure and is what every decision
  used.
