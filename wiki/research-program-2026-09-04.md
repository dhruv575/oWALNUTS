# Research program 2026-09-04: the 0.2 program — make it usable, then make it competitive

Status: **complete through WP37A; WP37B is paused incomplete and no sampling
process is running.** Everything through WP37A and the append-only
Windows BridgeStan lifetime diagnostics is committed in the current `0.2.0`
release tree; nothing is pushed, tagged or published. WP37B remains off-main
on `wt/reverse-coarsening-order`: 73 of 84 planned cells were launched, the
first state-space cell failed, and 11 cells were never launched. The
owned-one-worker mitigation passed its final Windows GNU diagnostic, but
publication remains blocked on Windows MSVC, Linux/macOS and package/wheel
verification. The historical native root cause is not proven.
Companion documents:
`research-program-2026-08-31.md`
(the programme that produced `0.1.0-beta.2`), `research-ledger-2026-08-31.md`
(completed studies WP22–WP37A, including subordinate WP35A, plus a provisional
WP37B pause record),
`release-0.2.0.md`.

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
subsequent study (WP24–WP37A) exists because of something it found. Item 3 was
answered **no** by its own evidence.

## What is in the release tree

**A small API.** `owalnuts::sampler` exposes 30 top-level public names/items
across its builder, posterior/result, configuration, target, diagnostic and
control surfaces. `Sampler`, `Posterior`, `Metric`, `Adaptation`, `Tuning`,
`Limits` and `Init` remain the primary user-facing path, rather than an
exhaustive inventory. Every sampling path is a thin wrapper over one
`walnutpie` entry point and is tested to produce bit-identical draws to calling
that facade directly. The research-only facades (projected and pooled
arrowhead, the `direct_original_q` family, the research evaluation limit)
moved behind a `research` Cargo feature, off by default. `walnutpie` remains
public and frozen; `ALGORITHM_REVISION` never changed during this programme.

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
`owalnuts.DEFAULTS`, `init="uniform"`, `summary()`, `from_stan()` on Linux and
macOS, and the numba `cfunc` path. Windows 0.2 disables `from_stan` and direct
Python BridgeStan operations because those paths do not use the Rust owner
backend. A `wheels.yml` matrix builds abi3 wheels for Linux x86_64 and aarch64,
macOS x86_64 and arm64, and Windows, with an sdist that vendors the
path-dependency crates and PyPI trusted publishing gated on a tag. The name
`owalnuts` is available on PyPI. The non-Windows legs have not been exercised.

## The defaults changed nine times, each behind evidence

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
| chain rescue `restart_from_best` → none | WP36 `chain_rescue_v2` | `two_hit` failed its conjunctive gates and the registered fallback selected `no_rescue`; explicit rescue policies remain available |

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

v6 is the historical full-default run during the temporary WP33
`restart_from_best` default. It has the strongest gate count but did **not**
meet its preregistered release rule: a passing `one_comp` cell has max |z|
4.023 and one `sblrc` oWALNUTS subprocess exited without a result, so the
fixed-16 efficiency criteria are unevaluable. WP36 subsequently selected
`no_rescue`, and commit `87d8817` restored that default. v5 therefore again
matches current sampler behavior and remains the release headline admitted by
its own rule; v6 must be reported beside it as the record of the temporary
WP33 default.

No posteriordb v7 is required before release. This is not result-driven
benchmark substitution: the final sampler restores v5's no-rescue defaults,
and tests directly compare default output with an otherwise identical explicit
custom no-rescue warmup, including empty rescue telemetry. A future v7 becomes
necessary if an automatic cross-chain action is reintroduced, because that
would again change the behavior measured by v5.

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

That original replicated path later exposed a separate Windows native
lifetime failure class. `bridgestan_lifetime_v1` tested resident DLLs plus
joined Rayon workers, but its fixed arm still faulted in 8/180 children and
was rejected. `bridgestan_owned_worker_v1` moved every native call onto one
owned OS thread per target and added a process-global native-call mutex. Its
final fixed-only qualification completed 540 ordinary and 180 concurrent
four-target children with zero faults or correlated Event 1000 records
(one-sided 95% upper bound 0.415210% for 0/720), exact settings/counters and
one effective replica throughout. Sampling cost was 3.1–5.1x the historical
four-replica comparator. This is a narrow Windows GNU mitigation result, not
proof of root cause or general native-runtime safety.

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

**Fixed `delta = 2` is not qualified for the preregistered adaptive-to-2 path
(WP37A).** All 84 funnel, strict noncentered Eight Schools and analytic 100-D
Gaussian children were one-shot valid. F1, F2, F5, E1–E4 and G1–G4 passed;
F3 and F4 failed. Funnel pooled accuracy passed, and fixed2 had 13 retained
divergences across six seeds versus fixed1's 14 across four, but each arm had
only 2/12 healthy seeds and the healthy sets were disjoint. Eight Schools E3
was 1.0478 and Gaussian G3 was 1.0168. The mechanical decision is
**`FIXED2_NOT_QUALIFIED_FOR_ADAPTIVE_TO_2`**. This blocks only WP37A's naive
adaptive-to-2 path, not every possible target-adaptive rule. No implementation
or default change is authorised by this study.

The honest conclusion is a statement about the target class. **WALNUTS wins
where stiffness is localised** — Neal's funnel, the T=1000 state-space path,
`gp_pois_regr` and the centered eight schools, where the NUTS implementations
diverge and it does not — **and reduces to NUTS with overhead where stiffness is
uniform.** The v5 gate lead is a robustness lead, not a per-gradient lead:
oWALNUTS finishes cleanly where CmdStan and nutpie leave a chain stuck or
divergent, while still spending more gradients per effective sample on healthy
models (0.67–0.95x).

## Open investigations after the paused WP37B, in priority order

1. **Qualify the narrow BridgeStan mitigation beyond Windows GNU.** WP35A and
   WP36 reproduced the replicated-target failure class; the first
   resident/scoped mitigation still faulted in 8/180 children and was
   rejected. The owned-one-worker/process-global-serialization backend passed
   the final 720-child Windows GNU diagnostic, but the root cause remains
   unestablished. Exercise that exact backend on Windows MSVC, then Linux and
   macOS as applicable. Keep the WP35/WP36 and both lifetime-study raw trees
   immutable. Nothing in these failures identifies a defect in the core Rust
   sampler.
2. **Release/package verification.** Exercise the core crate on Windows MSVC
   and Linux, and the Python/BridgeStan package jobs across Windows, manylinux
   x86_64/aarch64 and macOS x86_64/arm64, including the sdist. Expert Rust
   `StanTarget` use is mitigation-qualified only on Windows GNU; Windows
   Python `from_stan` and direct Python BridgeStan remain disabled.
   Publication remains blocked until this matrix is complete.
3. **Resolve the paused reverse-coarsening study before starting another
   kernel experiment.** WP37B preregistered finest-to-coarsest versus
   coarsest-to-finest reverse checks at fixed `delta = 1`, as an explicit
   opt-in qualification only. The first 72 cells (four posteriordb targets,
   funnel and Gaussian) returned authenticated results. The 73rd launch, the
   incumbent-order `sspd-11` seed 96101 cell, exited 1 after 23.13 s with
   `canonical log density or gradient is not representable as finite f64`
   on chain 1, transition 1; it wrote no raw result. The unchanged runner then
   stopped, leaving 11 state-space cells unlaunched. Under the frozen rule the
   study is incomplete and cannot qualify the candidate. No cell was rerun,
   no result was merged, and no default changed. Preserve and archive the
   partial record before deciding whether a fresh protocol should omit or
   repair that target; any new evidence decision requires fresh seeds.
4. **Further target-adaptive `delta` research, after reverse-coarsening.**
   WP37A mechanically nonqualified the preregistered naive adaptive-to-2 path:
   fixed2 did not meet the funnel gross-safety and absolute healthy-count gates.
   The result does not rule out every target-adaptive rule that could reach 2,
   but no such rule is next in the kernel queue or authorised for implementation.
5. **Optional rescue research, not a default.** WP36 resolves the 0.2 default:
   no automatic cross-chain action. A future study may test an observe-only
   warning or a narrowly scoped step-only action. It must preserve original
   chain attribution and retain the origin classifier limitation: WP36 found
   only pathological/frozen ARMA and `lotka_volterra` origins and zero HMM
   origins, so it provides no proof of genuine mode destruction.

## Method notes worth keeping

- Every evidence study was preregistered with a frozen `protocol.json` and fresh
  grep-verified seeds before the first cell, and several were decided *against*
  the hypothesis that motivated them (WP26, WP27's default, WP29's stanreg arm,
  WP34, WP36's candidate). The WP31 pair was a labelled post-hoc flip validated
  by WP32; WP33's preregistered rule temporarily enabled rescue, and WP36's
  frozen fallback restored no rescue.
- Bit-identity was the safety rail throughout. `tests/kernel_fingerprint.rs`
  pins the `walnutpie` defaults, and every performance or refactoring change had
  to reproduce it; two changes (WP30's cache, WP33's driver refactor) were
  accepted specifically because they were bit-identical.
- Wall times were measured on a shared machine with other agents running, so ESS
  per gradient is the machine-independent figure and is what every decision
  used.
- Future high-volume stress studies should consolidate heartbeat/process
  evidence into reviewable archives or indexed bundles. Existing study
  history and raw files remain append-only and are not rewritten.
- A stopped one-shot study is still a result. WP37B's 72 successful cells,
  one process-valid fatal target failure and 11 unlaunched cells must remain
  distinguishable; the failed cell must not be deleted or rerun.
