# oWALNUTS

`owalnuts` is a Rust implementation of **WALNUTS**, the Within-orbit Adaptive
Leapfrog No-U-Turn Sampler (Bou-Rabee, Carpenter, Kleppe, Liu; *JMLR* 27,
2026). It is NUTS with a second time scale: every macro leapfrog step is
subdivided into micro-steps, and the number of micro-steps is chosen per
step so that the local energy error stays under a threshold `delta`. Fine
steps are spent only where the curvature demands them, which is what lets it
sample multi-scale targets such as Neal's funnel without the bias fixed-step
NUTS shows there. The kernel is derived from, and tested leaf-for-leaf
against, the Flatiron reference implementation
[`walnutpie`](https://github.com/flatironinstitute/walnutpie) (MIT); the
public API is a small builder, `owalnuts::sampler`, over a complete
facade, `owalnuts::walnutpie`. Version `0.3.0`; kernel revision
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`.

> **Defaults changed since 0.2.0** (released in 0.3.0, the trapped-chain
> guard on `main` after it; see [`CHANGELOG.md`](CHANGELOG.md)). The kernel,
> `ALGORITHM_REVISION` and the kernel fingerprints are unchanged; each old
> behaviour is one builder call away.
>
> - **Best-of-16 starts.** `Init::default()` and `run_from_random_starts` keep
>   the highest-log-density of 16 evaluable uniform(-2, 2) starts per chain,
>   so draws for a given seed differ from 0.2.0; decided by the preregistered
>   confirmation `STUDIES/init_rule_confirmation_v1` (WP52: 1.254x ESS per
>   gradient, 42 vs 42 gates) [E20].
> - **`NonfinitePositionPolicy::RejectLeaf`.** An integrator overflow becomes a
>   rejected zero-density leaf instead of ending the whole run, and any run
>   without the event is bit-identical; decided by
>   `STUDIES/nonfinite_policy_requalification_v1` (WP54: bit-identical on
>   73/73 cells, 75 vs 73 runs completed) [E21].
> - **Fixed `Metric::dense()` warmup.** Dense warmup now uses per-transition
>   seeding, Stan's dense regularisation and a symmetrised precision; an
>   engineering decision after `STUDIES/dense_metric_confirmation_v1` (WP51:
>   3.21x the diagonal per gradient against 0.055x for the old dense
>   defaults), whose own frozen rule failed (40 vs 43 gates) [E19].
> - **Trapped-chain guard** (`DEFAULT_TRAPPED_CHAIN_RESTART`, after 0.3.0).
>   With three or more chains on the identity or diagonal metric, a chain
>   whose step at the close of the first slow warmup window is below 0.01x
>   the chain median restarts from an independent best-of-16 start; draws
>   are unchanged unless a chain fires. Decided by the preregistered
>   confirmation `STUDIES/trap_guard_confirmation_v1` (WP90: SV trapped
>   chains 8/480 to 0/480, 282/282 unfired cell pairs bit-identical, 92 = 92
>   gates) [E54]. `WarmupConfig::without_trapped_chain_restart()` opts out.

## Quick start

```toml
[dependencies]
owalnuts = "0.3.0"
```

Implement `Target` (log density and gradient in one call, unconstrained
`f64` coordinates) and run the sampler at its defaults. This is
[`examples/readme_quick_start.rs`](examples/readme_quick_start.rs), which CI
runs:

```rust
use owalnuts::diagnostics::Summary;
use owalnuts::sampler::{Sampler, Target, TargetError};

struct Gaussian;
impl Target for Gaussian {
    fn dimension(&self) -> usize { 5 }
    fn log_density_gradient(&self, q: &[f64], grad: &mut [f64]) -> Result<f64, TargetError> {
        for (g, x) in grad.iter_mut().zip(q) { *g = -x; }
        Ok(-0.5 * q.iter().map(|x| x * x).sum::<f64>())
    }
}

let posterior = Sampler::new()
    .warmup(1_000)
    .draws(1_000)
    .chains(4)
    .seed(0x5eed)
    .run_from_random_starts(&Gaussian)?;   // best of 16 uniform(-2, 2) starts per chain

let summary = Summary::from_output(posterior.inner(), None)?;
println!("{summary}");                     // mean, sd, MCSE, quantiles, ESS, R-hat, health
```

The defaults are tuned for funnel-shaped posteriors as well as ordinary
ones: eight refinement levels, which is what keeps the quick-start
configuration unbiased on Neal's funnel (see "Where it shines").
`Summary` prints a Stan-style table (rank-normalised split R-hat, bulk and
tail ESS, MCSE, 5/50/95 % quantiles; each estimator matches ArviZ to 1e-6)
followed by the sampler health per chain and pooled: divergences, invalid
evaluations, depth-cap stops, refinement exhaustions, mean tree depth, target
calls, step size. `posterior.draws()` iterates retained positions as
`&[f64]`; `posterior.chains()` gives per-chain draws, diagnostics, telemetry
and metadata; `.run(&target, &starts)` takes explicit starts, one per chain.

One line each for the other front doors:

- **CmdStan CSV**: `export::CmdStanCsv::new().with_log_density(&target).write_dir(posterior.inner(), "out", "chain")?`
  writes `out/chain-1.csv ...` that `arviz.from_cmdstan` loads directly.
- **Python**: `pip install maturin` then `maturin develop --release` in
  [`integrations/python`](integrations/python/README.md);
  `owalnuts.sample(logp_and_grad, dim=10, warmup=1000, draws=1000, seed=1).summary()`,
  with `from_jax`, `from_torch` and `from_pymc` adapters. For PyMC models use
  `from_pymc(model, gil_free=True)` with `threads=4`; for hand-written
  densities a numba `from_cfunc` (within 1.15x of a native Rust target);
  plain callables, the default `from_pymc` and `from_jax` at `threads=1`
  (`from_jax` adds 20–40 µs per gradient). nutpie is 1.4–1.9x faster per
  second on smooth and larger hierarchical PyMC models and fails
  noncentred Eight Schools [E44].
- **Stan models**: [`owalnuts-bridgestan`](integrations/bridgestan/README.md)
  wraps a BridgeStan-compiled model as a `Target`
  (`ReplicatedStanTarget::load(so, preload, data, seed, threads)` for
  multi-chain runs). On Windows the Rust integration by default records the
  requested replica count but uses one effective owned worker per target and
  serializes all native BridgeStan calls process-wide (see "Threads and
  chains" for the opt-in static-runtime dispatch); Python `from_stan` and
  direct Python BridgeStan operations are disabled there for 0.2.
- **Rust autodiff**: [`owalnuts-autodiff`](integrations/autodiff/README.md)
  turns `fn log_density<S: Scalar>(&self, q: &[S]) -> S` into a `Target`
  with a reverse-mode tape, a few times the cost of a hand-written gradient.

## Diagnostics

`Summary` (and `posterior.chain_warnings()`) also prints observe-only
`warning: chain k ...` lines; computing them never changes a draw.

- **A restarted chain** (WP90): a chain whose step at the close of the
  first slow warmup window was below 0.01x the chain median reran from an
  independent best-of-16 start; `RunTelemetry::trapped_chain_checks` (Python
  `trapped_chain_checks`) records every chain's check and the restart.
  Nothing is copied from another chain, so the chains remain independent
  starts and independent-chain R-hat stays valid [E54].
- **A chain that disagrees with the others** (WP44, WP74): a collapsed
  end-of-warmup step, a median log density far below the other chains' at
  the end of warmup or over the draws, or a chain whose removal alone brings
  R-hat under 1.01 [E22]. When R-hat fails and no single chain explains it,
  a pairwise check groups chains whose pair R-hat is at most 1.01 and flags
  every chain outside the largest group (if that group has two or more
  chains). That reports mode splits with two chains per mode or a chain
  caught crossing between modes: 5/5 split cells in WP74, against 1/5
  without it, and no finding on 43 healthy posteriordb cells [E40]. It needs
  at least three chains, misses a split in which no two chains agree, and
  does not replace the R-hat / ESS gates. The older step and warmup-density
  checks fired on 3 of those 43 healthy cells (transient warmup dips).
- **Rejected nonfinite positions**: `warning: chain k rejected n nonfinite
  positions during warmup`. The default `RejectLeaf` rescue records no
  divergence, so this line (or `WorkTotals::nonfinite_position_rejections`)
  is where an integrator overflow shows [E21].
- **Zero divergences does not rule out a funnel.** On centred hierarchical
  models a run can be wrong with no divergence at all. In WP55, 11 of 12
  wrong cells on the funnel, centred Eight Schools, `seeds_centered` and
  centred radon had zero retained divergences, and the R-hat / bulk ESS /
  tail ESS gates caught every one of them [E23]. This is not specific to
  WALNUTS refinement: in posteriordb v7, CmdStan and nutpie also recorded
  zero retained divergences on every `seeds_centered` cell, and failed it on
  the same `sigma` [E26]. Check the R-hat / ESS gates, not the divergence
  count.

## Threads and chains

Chains run in parallel on up to `threads` worker threads (WP45, [E24]):

- `threads` above `chains` does nothing; the driver clamps it to the chain
  count. Draws are bit-identical at every thread count.
- Wall time is bounded by the slowest chain. Chain lengths differ by target
  (max/mean gradients at 16 chains were 1.51 on a 100-D Gaussian and 3.05 on
  a local-level model), so one straggler sets the wall.
- **Windows BridgeStan:** the default owned worker serialises every native
  call. For multi-chain throughput build the model and `tbb.dll` with the
  static mingw runtime (`integrations/bridgestan/tools/build_static_runtime.py`)
  and load with `ReplicatedOptions::concurrent_if_static_runtime()`: 3.2x
  (sblrc) / 4.0x (arK) contended sampling wall with bit-identical draws
  (WP50C). It is opt-in, not the default, because the WP50D confirmatory
  gate was not supported (1/1000 static children failed, with a sampler
  nonfinite-position error rather than a crash) [E25].
- **Linux BridgeStan (x86_64, glibc):** the default concurrent-replica
  dispatch is qualified (WP65, [E30]): 0/500 child faults, draws bit-identical
  to the serialised path, 4.0–5.4x gradient throughput at four callers, and
  wall per gradient 0.96x CmdStan's on the fixed-16 models (pinned,
  co-tenanted, one seed). Serialising the calls costs 3.6x. Build without
  `STAN_THREADS` on Linux too: a threaded library costs up to 1.57x per call
  (`arK`) and is not unloaded on drop. macOS, aarch64 and Windows multi-worker
  dispatch remain unqualified.

## Warm continuation

`Sampler::start_session` serves one fixed target of fixed dimension: one
`adapt()`, then `draw(n)` chunks. For a posterior that must be refreshed
when the target changes (new data, a new latent coordinate), the warm path
of WP84 ([E52]) is a library call since WP87: `Posterior::warm_state()` (or
`SessionChunk::warm_state()`) carries each chain's last position, its
adapted step size and its adapted diagonal mass; `WarmState::extend_to(n,
0.0, 1.0)` appends coordinates for a larger target; and
`Sampler::new().draws(k).seed(s).run_warm(&new_target, &state)` runs `k`
transitions per chain with no warmup, no adaptation, each chain on its own
frozen step and metric (chain `c` is bit-identical to the single-chain
`run` with seed `s + c`, `Metric::fixed_diagonal`, `Adaptation::None` and
`Tuning::step_size`; `tests/warm_continuation.rs`). The result is an ordinary
`Posterior` whose `warm_state()` is the next tick's state. It does not
re-adapt, it carries identity/diagonal metrics only (dense and structured
runs error), the fill of new coordinates is the caller's decision, and the
library does not validate that `k` draws refresh the posterior to any
accuracy: on the 250-return SV model of WP84, 50–200 draws per chain stayed
calibrated over 100 ticks (20–80 ms per tick) but did not reach the R-hat
1.01 / reference-MCSE bar; scored against the quote itself (post hoc), 200
draws per chain kept the next-period sigma P50 within 2 % and the P95
within 5 % of the reference on 97 % / 98 % of ticks, 50 draws on 74 % /
78 %. Python: `result.warm_state()`,
`state.extend_to(dim)`, `owalnuts.sample_warm(target, state, draws=k, seed=s)`.

For a loop of such refreshes, `Sampler::new().seed(s).threads(t)
.start_warm_session(target, state)` (WP91) keeps the worker thread, a
pool of `t` workers and every per-chain input resident: `refresh(k)` runs
`k` transitions per chain and hands back the kernel's own draw buffers,
`state()` is the current state, `retarget(new_target, new_state)` swaps
both (a new dimension is allowed) and `close()` joins. Call `n` of a
session is bit-identical to `run_warm` with seed `s + n * chains` on the
state before the call (`tests/warm_session.rs`). `WarmState::remap(dim,
map, fill)` rebuilds the state for a new coordinate layout (new coordinate
`j` carries old coordinate `map(j)` or the fill), and
`WarmState::shift_window(drop_front, append, fill)` is the fixed-lag move
(drop the oldest latents, append new ones at the prior fill), so a
constant-dimension window and the growing WP88 state are both one call.
One laptop run of `examples/warm_session_bench.rs` (contended machine,
indicative; median wall per call, 4 chains x 4 threads, release): on the
WP84 shape (253 coordinates) `run_warm` 2.1 ms versus the session 1.6 ms
at 5 transitions per chain, 3.6 versus 3.0 ms at 10, 19.5 versus 19.8 ms
at 50; on a 50-latent fixed-lag window (53 coordinates) 0.70 versus 0.37
ms at 5, 1.07 versus 0.67 ms at 10, 4.3 versus 3.5 ms at 50; single-
threaded the two are within noise. The removable per-call overhead is
about 0.3-0.5 ms with a 4-thread pool; the rest is the kernel's own work
(300-3,000 gradients per call at 1.7-12 us each), so a sub-millisecond
refresh comes from few transitions on a small window (the 53-coordinate
window at K = 5), not from the session alone. Python: `owalnuts.WarmSession(target, state, seed=s,
threads=t)`, `session.refresh(k)`, `session.retarget(target, state)`,
`state.shift_window(1, 1)`.

When the tick needs a few quote quantities rather than the draws,
`session.refresh_functionals(k, &functionals)` (WP95) evaluates
registered `Functional`s (`FunctionalFn::new(outputs, |q, out| ...)`, or a
C callback through `RawFunctional`) on every retained draw inside the
chain loop and returns a `FunctionalChunk`: per chain the `k x outputs`
values, streamed moments per output, the diagnostics and `warm_state()`,
but no draws unless asked (`Functionals::retain_draws`), with pooled
`mean` / `variance` / `quantile(output, q)`; `Sampler::run_warm_functionals`
is the one-shot form. The values are the functionals of `refresh`'s draws
bit for bit and the draws do not depend on the functionals
(`tests/warm_functionals.rs`). The retained result shrinks from `k x dim x
chains x 8` to `k x outputs x chains x 8` bytes (K = 50 on the WP84 shape:
395 KiB of draws against 9.4 KiB for six outputs) and the peak live memory
of a call with it (597 KiB against 279 KiB at K = 50 and 4 threads; the
rest is the kernel's own per-transition workspace, which no result
layout changes); wall per call is within noise of `refresh` because the
functionals cost far less than the kernel's gradients. Python:
`session.refresh_functionals(k, [owalnuts.from_cfunc_functional(f, 1)])`
and `chunk.quantile(0.95, 0)`; a Python callable functional works too but
attaches the interpreter once per draw per chain (0.16-0.55 ms each on
the SV targets).

## Where it shines

Every number below is from a preregistered, checksummed study in
[`STUDIES/`](STUDIES/); the Evidence list at the end links each one.

- **Neal's funnel is sampled without bias.** At the paper's tuning,
  4 x 50,000 draws give tail mass `P(omega < -5)` = **0.0474** against the
  exact 0.0478 (the reference implementation at identical tuning: 0.0477),
  with zero divergences; fixed-step NUTS is biased on this target, and so
  was the pre-`v9` kernel (0.0971). [E1] At the **sampler defaults**
  (adapted diagonal metric, dual averaging, `h0 = 0.5`) the tail mass is
  within `|z| <= 2` of exact on three fresh seeds (0.0412, 0.0346, 0.0897)
  because the default is eight refinement levels; at four levels it was
  half the exact value, and a one-level NUTS-like control never draws
  below `omega = -5` on two seeds. The pooled estimate is right but the
  funnel does not mix *well* at the defaults (one chain per seed adapts
  to `h ~ 0.01`, `omega` R-hat 1.01-1.04); `Tuning::new().max_error(0.5)`
  mixes better there at a 21 % cost on a 100-D Gaussian. [E11]
  Over 30 fresh seeds (WP53, 4 x 2,000/20,000) the default's tail estimate
  is biased low: mean z -0.42, 4/30 seeds beyond |z| 2 and all low, pooled
  P(omega < -5) 0.0458 +/- 0.0014 against the exact 0.0478, with no
  divergences or warnings to show for it. `delta = 2` shares the deficit
  (pooled 0.0455) with no seed beyond |z| 2. A three-seed |z| <= 2 funnel
  gate fails the unchanged default about 35 % of the time, so read
  single-seed funnel z values as noise and pooled tail mass as the check
  [E29].
- **Long state-space paths mix at depth 3–4.** On an exact Gaussian
  state-space model at `T = 1000`, supplying the posterior-precision
  tridiagonal metric (`Metric::Structured`) gives ESS per target call
  **~1,000x** a prior-based metric and 4.8x the identity, at Monte-Carlo
  accuracy against the closed-form posterior. [E2]
- **Eight Schools throughput on a strict matched track.** Noncentered Eight
  Schools, 4 chains, 1,000/1,000, one thread: the conservative minimum over
  seven seeds and six functionals is **12,830 bulk / 10,346 tail ESS/s**
  against CmdStan 6,290 / 3,951, BlackJAX 5,645 / 4,195 and NumPyro
  5,241 / 4,050 on the same track. [E3]
- **Zero divergences where NUTS diverges.** In the posteriordb benchmark,
  oWALNUTS passes every gate on noncentered eight schools (3/3 seeds;
  CmdStan 1/3, nutpie 0/3) and `gp_pois_regr` (up to 3/3; CmdStan 0/3 with
  9–16 divergences, nutpie 0/3 with 120–822), with no divergence on
  either. [E4]

## Where it does not (yet)

**posteriordb v7 (WP56), the current defaults: mixed.** At the defaults
listed under "Defaults changed since 0.2.0", oWALNUTS passes **43/51** house
cells against CmdStan 34 and nutpie 26. The run used the 17 posteriordb
posteriors, every sampler at its defaults, 4 chains, 1,000/1,000 and three
fresh seeds. The gates were rank R-hat <= 1.01, bulk and tail ESS >= 400 and
zero retained divergences, with CmdStan 2.39.0 and nutpie 0.16.8 on the same
seeds. No passing reference cell is above |z| 3.82. All 66 oWALNUTS cells
completed with no error, timeout or frozen chain. The funnel is unbiased on
every seed (z +1.69, -0.59, +0.84). [E26]

Five hard posteriors joined the benchmark in v7 (GLMM_Poisson,
`seeds_centered`, kilpisjarvi, grsm and centred radon). There oWALNUTS
passes 6/15, against CmdStan 7 and nutpie 3: 3/3 on kilpisjarvi and grsm,
and 0/3 on GLMM_Poisson, `seeds_centered` and radon. Those three fail on a
slow `sigma` or `beta[1]`, the same parameters that defeat the competitors
(CmdStan passes one radon cell; nutpie none). [E26]

ESS per gradient is **0.83x CmdStan's over 18 Linux seeds** (median of
paired per-seed ratios over the fixed-16 models, seed-bootstrap interval
[0.79, 0.94]; WP72, [E38]). The earlier six-seed figures, 0.76 on Windows
and 1.21 on Linux, were both seed noise: on six seeds the interval spans
0.7–1.6 on either platform. Gates over the same 288 cells are 239 for
oWALNUTS, 198 for CmdStan and 163 for nutpie 0.16.8 (WP76, [E42]); per
gradient oWALNUTS is 0.70x nutpie [0.65, 0.96], and per second on Linux it
is 0.89x CmdStan [0.85, 1.00] and 0.93x nutpie [0.87, 1.28], both intervals
reaching 1. The honest line over 18 seeds: the most reliable of the three
by a wide margin, a little behind per gradient, about even per second.
v7's own three seeds gave
0.708 over the 15 complete fixed-16 models, against v6's 0.848; a
preregistered three-seed extension (WP62) gave 0.810 on the new seeds and
**0.761 pooled over six**, with a leave-one-seed-out interval of
[0.740, 0.822] [E28]. Pooled over 96 cells oWALNUTS passes 80 against
CmdStan's 62. The one loss that survives both seed sets is `accel_gp`
(0.35x); `one_comp` (0.50x -> 1.63x) and `hmm_drive_0` (0.66x -> 0.98x) swung
with the seeds. Wall per gradient is 1.85x CmdStan's, because the Windows
owned worker serialises BridgeStan and the machine was contended. ESS per
second is 1.23x nutpie's.

The same protocol on Linux (WP64, 16 dedicated cores, pinned and
co-tenanted) reproduces the pass counts within one cell per block: oWALNUTS
44/51, 7/15 and 41/48 (one `seeds_centered` cell now passes), CmdStan 33, 5
and 31, nutpie 27 and 5. No cell is bit-identical across platforms (the
start search matches; runs diverge by warmup iteration 50, as libm differs).
The per-gradient headline is platform- and seed-dependent: pooled over six
Linux seeds it is **1.21x CmdStan**, because CmdStan's chain sits in
`hmm_drive_0`'s second mode on 4 of 6 Linux seeds (2 of 6 on Windows), and
0.86x without that model (Windows 0.75x). Wall per gradient falls to 0.94x
CmdStan's with the concurrent-replica dispatch, and ESS per second is 1.22x
CmdStan's and 1.45x nutpie's on those six seeds (over 18 seeds, 0.89x and
0.93x; WP76). The robustness study (WP72, 12 further seeds) fixed the
headline statistic above. [E34]

v7 did **not** pass the v6 release rule. Its per-gradient clause (>= 0.75
CmdStan) failed: the value was 0.708, and the clause was formally
unevaluable because one CmdStan `lotka_volterra` cell errored. Its wall
clause failed too. That per-gradient clause is now known to be seed-noisy.
Paired reruns on the same seeds attribute the 0.848 -> 0.708 change neither
to best-of-16 starts (1.061x uniform, WP60) nor to removing chain rescue
(1.023x, WP61), but to seed-to-seed variation. The 3-seed geomean moves by
about 0.1 between seed sets with no code change behind it [E27]. The pass
counts are therefore the headline. Under its frozen rule, v7 does not
replace v5 as the last release-qualified benchmark. v5 and v6 follow as
history.

**History: v5 and v6.** The last breadth benchmark admitted by its
preregistered release rule is
[`STUDIES/posteriordb_bench_v5`](STUDIES/posteriordb_bench_v5/README.md),
on the same 17 posteriors and protocol, at the 0.2.0 defaults. [E15] (v3 on
the pre-WP31 defaults, kept as history: 35/51, 0.34x CmdStan per gradient
[E4].)

WP33 subsequently made warmup restart-from-best chain rescue the default.
The then-current-default validation, `posteriordb_bench_v6`, passes **45/51**
cells against CmdStan 34 and nutpie 29 with no frozen chain, but did not meet
its frozen release rule: one passing `one_comp` cell has max |z| 4.023 and one
`sblrc` sampler subprocess exited without a result, leaving its fixed-16
efficiency gates unevaluable (observed 0.848x CmdStan per gradient over the 15
complete models). WP36 then mechanically selected `no_rescue`: its
preregistered completeness gate failed after seven process faults, and
`two_hit` failed its conjunctive efficacy, nuisance-reduction, funnel,
origin-safety and efficiency gates. That failure alone did not select
`no_rescue`; it advanced the mechanical rule to the `current` fallback check.
`current` had registered red lines in four origin-overwrite cells (five
events) plus unknown run history for HMM/92104, so the fallback selected
`no_rescue`. The final 0.2 default therefore returns to the plain multi-chain
warmup used by v5. The v5 numbers below are the 0.2.0 release figures; v6
remains the historical record of the temporary WP33 default and must be read
beside it. [E16, E17, E18]

> **Historical WP35 replay:** do not run
> `STUDIES/posteriordb_bench_v6` from the current tree and call it a WP35
> reproduction. Check out the recorded WP35 study revision `8d3a7b5` (source
> under test `aa4510f`) first. At current HEAD,
> `Adaptation::default()` intentionally means no rescue, whereas WP35 measured
> the temporary restart-from-best default.

v5 (0.2.0 defaults):

- **More cells pass than CmdStan or nutpie.** oWALNUTS passes **42/51**
  cells; CmdStan 36, nutpie 28. Twelve models at 3/3 against ten and eight.
- **ESS per gradient is still below CmdStan on ordinary posteriors.**
  Geometric mean **0.82x** CmdStan over the 16 models where CmdStan is
  healthy, 0.67–0.95x per model with no exception; 1.07x over all 17 only
  because CmdStan and nutpie each lose two `arma11` seeds to a chain that
  never leaves its start (oWALNUTS 3/3 there). Against nutpie 0.84x per
  gradient. The residual is the kernel (reverse-coarser stops on refined
  leaves and orbit length, [E13]), not warmup.
- **Wall time and ESS per second are ahead.** Wall per gradient **0.80x**
  CmdStan's; ESS per second **1.40x** CmdStan's and **3.09x** nutpie's
  (above CmdStan on 8 of 17 models, above nutpie on 14 of 16).
- **What still fails.** The centered eight schools fails every sampler on
  every seed; `accel_gp` (66-d GP) fails every sampler at 0.47x CmdStan per
  gradient; `hmm_drive_0` can put one chain in a second mode from a uniform
  start (one seed each for oWALNUTS and CmdStan here); `one_comp` is 1/3
  for oWALNUTS and CmdStan; `diamonds` still hits the depth-10 cap on
  250–540 transitions per seed. Bad starts no longer stall a chain: no
  frozen chain, no step collapse (`sblrc` 0/3 -> 3/3), zero retained
  divergences on every oWALNUTS cell.
- **Refinement rarely engages on these posteriors.** A refinement level
  above zero is selected on 1–3 % of retained transitions, so on ordinary
  models the kernel runs as NUTS, and its endpoint U-turn rule then costs
  0.75–0.9x per gradient against Stan's momentum-sum rule on Gaussian
  targets. On the posteriordb set, swapping in Stan's rule alone
  (`UTurnRule::MomentumSum`) is a per-model coin (1.06–1.12x geometric
  mean) because the default metric regularisation floors small posterior
  variances at 0.01 and hides it; with Stan's regularisation
  (`DiagonalMetricRegularization::Stan`) the two together are 1.51x the
  default per gradient over the 17 models and pass 41 cells against 35.
  The preregistered flip rule failed on the two cells no option passes
  (`hmm_drive_0`'s second-mode draw, the centered eight schools); the
  pair was made the default afterwards as a post-hoc decision and
  validated on fresh seeds in `STUDIES/posteriordb_bench_v5` [E15].
  [E5, E6, E12, E13, E14]

The wins measured so far come from funnel-type targets, from structured
metrics, from gates (fewer failed cells than either NUTS implementation on
the posteriordb set) and from wall time; per gradient, an ordinary
regression that CmdStan already samples cleanly still costs oWALNUTS
1.05–1.5x the gradients.

## Defaults and opt-ins

`Sampler::new()` with no other calls runs:

| Setting | Default | Why |
|---|---|---|
| warmup / draws / chains | 1,000 / 1,000 / one per start | Stan's shape |
| `Tuning::max_depth` | 10 | ablation over nine posteriordb models: 1.45x ESS per gradient and 17/18 gates against depth 8 [E7] |
| `Tuning::step_size` (`h`) | 0.5 | initial macro step; dual averaging adapts it |
| `Tuning::max_refinement_levels` | 8 | micro-steps down to `h / 128`; four levels halve the funnel's tail mass at the adapted step, eight are exact and never engage on Eight Schools or a 100-D Gaussian [E11] |
| `Tuning::max_error` (`delta`) | 1 | energy-error threshold per macro step |
| `Tuning::kernel_options` U-turn rule | `UTurnRule::MomentumSum` (Stan's generalised criterion) | **post-hoc default change after WP31**, validated by WP32: with Stan's metric prior it is 1.51x the endpoint rule per gradient over 17 posteriordb models; the frozen `v10` endpoint rule is `KernelOptions::default()` [E14, E15] |
| `Adaptation` | dual averaging to acceptance 0.8 | 75 / 25, 50, 100, ... / 50 windows (`gamma` 0.05, `t_0` 10, `kappa` 0.75); warmup exhaustion rule `AcceptUnlessDivergent` [E10] |
| `Metric` | adapted diagonal | Welford, regularised with Stan's prior (`DiagonalMetricRegularization::Stan`, **post-hoc default change after WP31**; the `v10` `TowardUnit` prior floors small variances at 0.01 and collapsed the step on `sblrc` / `arma11`) [E14, E15] |
| warmup chain rescue | none (`DEFAULT_CHAIN_RESCUE = None`) | `two_hit` failed its conjunctive gates; `current` then hit registered red lines in four origin-overwrite cells (five events) plus unknown HMM/92104 run history, selecting the WP36 fallback; default telemetry has no rescue records [E18] |
| trapped-chain guard | `DEFAULT_TRAPPED_CHAIN_RESTART` (`TrappedChainRestartConfig::guard()`: step ratio 0.01 at the close of the first slow window, three or more chains, identity and diagonal metrics only; an independent best-of-16 restart, at most once per chain) | WP90 default-flip confirmation on WP89's mechanism: SV trapped chains 8/480 to 0/480, posteriordb 92 = 92 gates at ESS per gradient 1.000, funnel 0 firings, 282/282 unfired pairs bit-identical; two `kilpisjarvi` firings on recovering chains at no cost; `ALGORITHM_REVISION` unchanged [E53, E54] |
| starts (`Init::default()`, `run_from_random_starts`) | `Init::best_of(16)`: highest log density of 16 evaluable uniform(-2, 2) starts per chain | WP52 default-flip confirmation: 1.254x ESS per gradient, 42 vs 42 gates; the gain is the `arma11` / `lotka_volterra` start lottery, the other 14 models are 0.862x [E20] |
| `Tuning::nonfinite_position` | `NonfinitePositionPolicy::RejectLeaf` | WP54: bit-identical wherever `Abort` completed (73/73), 75 vs 73 runs completed; `KernelTuning::default()` keeps `Abort` [E21] |
| initial evaluation | cached | one gradient per transition saved, draws bit-identical [E6] |
| `Limits` | admit the exact worst case | the worst case is a bound the run cannot exceed, so admission costs nothing |

Opt-ins, each one builder call:

- `Adaptation::Paper(PaperAdaptationConfig::default())`: the JMLR Appendix C
  rules (`delta` from the K-quantile rule, `h` so a fraction of macro leaves
  needs no refinement). On Neal's funnel from `delta = 1, h = 0.1` it is
  unbiased and 1.41x / 1.61x (bulk / tail ESS per call) the paper's own fixed
  funnel tuning [E8]; on posteriordb it is at parity with dual averaging
  (geomean 0.995) and robust on the cells that froze under its v3 defaults
  [E4, E9]. See `examples/funnel_paper_adaptation.rs`.
- `Adaptation::Custom(WarmupConfig::new(0.8)?.with_warmup_exhaustion_rule(
  DEFAULT_WARMUP_EXHAUSTION).with_metric_regularization(DEFAULT_METRIC_REGULARIZATION))`,
  or `.without_trapped_chain_restart()` on any custom warmup: the pre-WP90
  default without the trapped-chain guard, bit for bit [E54].
- `Adaptation::Custom(WarmupConfig::stan_style(0.8))`: Stan's acceptance
  statistic, `init_stepsize`, metric prior and restart reference. 2.0x the
  default's ESS per gradient on correlated regressions but 12–16 % worse on
  three models and R-hat > 1.01 on two, so opt-in [E7].
- `Adaptation::Custom(WarmupConfig::new(0.8)?.with_chain_rescue(
  ChainRescueConfig::restart_from_best()))`: the WP33 immediate
  restart-from-best rescue remains an explicit bad-start robustness opt-in
  (25/27 cells against the plain driver's 21, including `lotka_volterra`
  0/3 -> 3/3). When it acts it copies another chain's state, invalidating the
  independent-start interpretation of ordinary R-hat; inspect
  `RunTelemetry::chain_rescues`. Observe-only, two-hit and pooling policies
  are explicit opt-ins through the same builder [E16, E18].
- **The pre-WP31 kernel rules** (the frozen `v10` endpoint U-turn rule and
  the unit-variance metric prior), for reproducing runs made before the
  default change:
  `Tuning::new().kernel_options(KernelOptions::default())`
  with
  `Adaptation::Custom(WarmupConfig::new(0.8).with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION).with_metric_regularization(DiagonalMetricRegularization::TowardUnit))`.
  The current defaults (`UTurnRule::MomentumSum` + `DiagonalMetricRegularization::Stan`)
  are a **post-hoc decision**: `STUDIES/joint_default_v1` preregistered a
  flip rule and failed it on two cells no option passes (`hmm_drive_0`'s
  arm-dependent second-mode draw, the centered eight schools), while the
  pair was 1.51x the old default's minimum bulk ESS per gradient over the
  17 posteriordb models (earnings 3.7x, sblrc 9.1x, arma11 2.3x, kidiq
  2.0x, hmm_example 1.9x, nes2000 1.5x; nothing below 0.94x among the
  models the old default passes), 41 cells against 35, funnel tail mass
  exact at both tunings with zero divergences and 1.29x on the Eight
  Schools strict track [E14]. The flip was decided after that result and
  validated on fresh seeds against CmdStan and nutpie in
  `STUDIES/posteriordb_bench_v5` [E15]. The two rules go together: the
  U-turn rule alone is a per-model coin (1.06–1.12x geomean) [E12], and
  the Stan prior under the endpoint rule is unstable on `earnings` (0.08x,
  R-hat up to 1.6: the short endpoint-rule orbits leave the window variance
  at the prior's floor) [E14].
- **The v5 breadth benchmark** is the honest figure for the final 0.2.0
  no-rescue defaults: CmdStan and nutpie rerun on fresh seeds 87101–87103 with
  preregistered predictions, all five held; 42/51 vs 36 and 28; 0.82x
  CmdStan per gradient on the healthy models (1.07x over 17 with `arma11`),
  0.80x wall per gradient, 1.40x / 3.09x ESS per second; funnel exact at
  the defaults on every seed [E15].
- `Init::best_of(16)`, the default (`run_from_random_starts`, `Init::default()`):
  per chain, 16 Stan-style uniform(-2, 2) starts, each redrawn until the log
  density and gradient are finite, keeping the highest log density (about 64
  extra gradient calls per run; WP43, confirmed as the default by WP52,
  `STUDIES/init_rule_confirmation_v1`). It removes most of the start lottery
  on `arma11` and `lotka_volterra`, but a highest-density start is not a mode
  oracle. It makes it less likely that the four chains visit a second mode
  (single-mode four-chain starts rose from 13 % to 23 % of seeds on a
  two-mode test target), so check `Summary::chain_warnings` as well as R-hat.
  On `hmm_drive_0` it held one chain in a second mode on 2 of 5 fresh seeds
  (gates 15/30 against uniform's 18/30 on six suspect models), and
  `chain_warnings` named that chain in both cells (WP60) [E27].
  `Init::uniform()` (`run_with_init`) is the CmdStan rule;
  `.run(&target, &starts)` uses your own.
- `Limits::new().max_target_evaluations(n)`, `.deadline(..)`, `.timeout(..)`,
  `.cancellation(..)`: an exact runtime evaluation ceiling and cooperative
  stopping; `.admit_conservative()` restores the 0.1 admission check.

## Structured metrics

`StructuredBlockMass` (`BidiagonalCholesky`, `ScaledAr1`; linear time),
`DenseMass`, `BlockDiagonalMass` and `LowRankArrowheadMass` are fixed momentum
covariances run from the `Sampler` through `Metric::Structured` and
`Metric::Dense`. For a Gaussian state-space path, the tridiagonal posterior
precision `Q_rw + diag(1/r_t)` as `M` whitens the whole path, so trajectories
U-turn at depth 3–4 at any `T` where a prior-based metric caps the tree
[E2]; `examples/state_space_path_metric.rs` shows it against the exact
posterior mean. When the right block depends on parameters being sampled,
`Metric::StructuredRefresh` rebuilds it from a caller-supplied
`StructuredMetricRefresh` at every completed slow warmup window and freezes it
before retention, with a typed `StructuredRefreshUpdate` per boundary.

## Dense metric (`Metric::dense()`)

`Sampler::new().metric(Metric::dense())` adapts a full dense metric during
warmup. It is **never selected automatically**, and the adapted diagonal
remains the default.

**When to use it:** correlated or collinear near-Gaussian regression and
autoregression posteriors. These are min-bulk-ESS-per-gradient ratios
against the diagonal default, posteriordb, 3 fresh seeds, all gates passed
in both arms [E19]:

| model | dense / diagonal |
|---|---:|
| `diamonds` | 98.7x (step 0.0036 -> 0.28; depth caps 10 % -> 0) |
| `nes2000` | 15.5x |
| `mesquite` | 15.3x |
| `arK` | 7.6x |
| `kidiq` | 5.4x |
| `earnings` | 4.5x |

**When not to:** GP-hyperparameter posteriors. At 1,000 draws `gp_pois_regr`
went 3/3 -> 0/3 gates: it is 1.73x per gradient, but it takes fewer
gradients per draw and the length-scale's ESS falls below 400. `accel_gp`
went 1/3 -> 0/3 at 0.38x. For GP models that must pass their gates, a
target acceptance of 0.95 is the measured opt-in: on `accel_gp` it passes
3/3 with 2.7x the ESS at 2.5x the gradients (WP70, [E35]). Funnels and
hierarchical scale problems also need care: on Neal's funnel the tail mass is exact, but there were 2 retained
divergences against 0 for the diagonal. Over all 17 models dense passes
40/51 gate cells against the diagonal's 43/51 (geomean 3.21x per gradient).
On fresh seeds in posteriordb v7's descriptive dense arm, `Metric::dense()`
passed 18/18 cells on the six correlated regressions above, at 13.4x the
diagonal default's ESS per gradient (`diamonds` 67.5x) with max |z| 3.05.
This supports dense as an opt-in for correlated regressions, not as a
default [E26].

Warmup uses per-transition seeding, Stan's dense regularisation and a
symmetrised precision. These have been the defaults since WP51. Earlier
builds used `Legacy` / `MeanVarianceShrinkage` / no symmetrisation, which was
0.055x the diagonal with 12/51 gates; that setting is still available
through `Adaptation::Custom` for reproduction
(`STUDIES/dense_metric_posteriordb_v1`, `STUDIES/dense_metric_confirmation_v1`).

## Oracle parity

Private test-only modules compare the kernel with pinned outputs of the
unmodified upstream headers (`cargo test oracle_tests`):

- `oracle/walnutpie/f5bba365`: 54 Gaussian macro-leaf, span, transition and
  transition-sequence units;
- `oracle/walnutpie/f5bba365_funnel_leaves`: 4,000 Neal's-funnel macro leaves
  across four tunings and `omega` in [-8, 4]: decision, level, endpoint,
  adaptation statistic and target calls agree to 1e-11 (kernel `v8`
  disagreed on 1,555);
- `oracle/walnutpie/f5bba365_invalid_leaves`: 4,000 leaves against a throwing
  wall target, pinning the `v10` rule that a recoverable failure refines like
  any over-tolerance micro-step.

Orbit-level parity on hard targets is covered statistically
(`STUDIES/funnel_bias_fix_v1`, `STUDIES/paper_funnel_reproduction_v1`), and
every `Sampler::run` path is bit-identical to the `walnutpie` entry point it
wraps (`tests/sampler_api.rs`).

## Known limitations

- The posteriordb gaps above: about 0.7x CmdStan per gradient (v7 [E26];
  0.34x on the v3 defaults), no throughput win
  on ordinary regressions, single chains stalled by bad starts on three
  models [E4, E10].
- Paper adaptation runs on the diagonal and fixed-operator facades only; the
  dense-adaptive, projected and pooled facades reject it.
- The `sigma_x -> 0` state-space funnel (`sspd-10`) is not sampled by any
  Euclidean sampler tested, NumPyro NUTS included; it needs a
  reparameterisation, not a metric [E2].
- On an exactly whitened Gaussian a fixed macro step can alias the
  tree-doubling schedule; there is no step-jitter option.
- Seeds reproduce runs bit for bit only under the same kernel revision, crate
  build, lock file, target architecture, operating system (the C math library
  sets the last bits of the draws; trajectory decisions agree across Windows
  and Linux) and thread-independent deterministic target.
- Cancellation and deadlines are cooperative; a callback that never returns
  cannot be interrupted. `ResourceLimits` are preflight ceilings for
  accounted allocations, not process memory.
- The Python, BridgeStan and autodiff crates are built from the tree, not
  published; the BridgeStan sampling tests need a locally compiled model.
- The core Rust sampler is distinct from optional Stan support. The Windows
  GNU Rust `StanTarget` owned-worker mitigation completed 540 ordinary and 180
  concurrent-target diagnostic children without a fault, but the historical
  root cause is not proven and sampling was 3.1–5.1x the four-replica
  comparator. Windows execution is therefore limited by default to one
  effective replica per target with a process-global native-call lock;
  static-runtime DLLs can opt into concurrent replicas (see "Threads and
  chains"). Windows MSVC and the
  Linux/macOS/package matrices remain release gates; Windows Python
  `from_stan` and direct Python BridgeStan calls remain disabled.

## API stability

`owalnuts::sampler`, `owalnuts::diagnostics`, `owalnuts::export` and
`owalnuts::walnutpie` are public and follow semver from `0.1.0`.
Research-only items (`OuterOrbitSelection`, `ResearchTargetEvaluationLimit`,
`ResearchRestartReferenceMultiplier`,
`DualAveragingAcceptance::AcceptedTrajectory`, the `direct_original_q`
family, the projected and pooled arrowhead facades) are exported from
`walnutpie` only with `features = ["research"]` and may change between minor
versions. `sampler::Tuning::default()` is not `walnutpie::KernelTuning::default()`:
the facade keeps the frozen replay defaults so pinned fingerprints hold.

## Research record

- [`wiki/README.md`](wiki/README.md): the wiki map. Start with the
  [decisions register](wiki/decisions.md), the
  [negative results](wiki/negative-results.md) and the topic pages under
  [`wiki/findings/`](wiki/findings/).
- [`wiki/release-0.3.0.md`](wiki/release-0.3.0.md): 0.3.0 changes, validation
  evidence, limitations and upgrade notes;
- [`wiki/release-0.2.0.md`](wiki/release-0.2.0.md): 0.2.0 changes,
  validation tables and limitations; [`CHANGELOG.md`](CHANGELOG.md) for the
  upgrade notes.
- [`wiki/research-ledger-2026-08-31.md`](wiki/research-ledger-2026-08-31.md):
  one checksummed entry per study.
- [`wiki/research-program-2026-09-04.md`](wiki/research-program-2026-09-04.md):
  the 0.2 program — what shipped, why each default changed, what the
  posteriordb benchmark falsified, and the open lines;
  [`wiki/research-program-2026-08-31.md`](wiki/research-program-2026-08-31.md):
  the program that produced `0.1.0-beta.2`.
- [`STUDIES/`](STUDIES/): every preregistration, runner, artifact and
  checksum.

## Toolchain

Rust 1.88 or newer. CI runs GNU 1.88 on Linux and Windows plus Linux stable:
tests (including all oracles), strict Clippy, `fmt --check`, `-D warnings`
rustdoc, examples and `cargo package`.

## Support and license

See [SECURITY.md](SECURITY.md) for scope. MIT; see [LICENSE](LICENSE),
[NOTICE](NOTICE) and [THIRD_PARTY.md](THIRD_PARTY.md) for the walnutpie
provenance.

## Evidence

- [E1] Funnel tail mass 0.0474 vs 0.0478, reference 0.0477, `v8` 0.0971:
  [`STUDIES/funnel_bias_fix_v1`](STUDIES/funnel_bias_fix_v1/README.md)
  (ledger `WP6-FUNNEL-BIAS-FIX-V9`).
- [E2] State-space path metric, depth 3–4 at `T = 1000`, ~1,000x prior-based,
  4.8x identity; `sspd-10` unsampled:
  [`STUDIES/exact_state_space_ground_truth_v1`](STUDIES/exact_state_space_ground_truth_v1/README.md)
  (`WP4-ESSGT-V1`),
  [`STUDIES/real_target_path_metric_v1`](STUDIES/real_target_path_metric_v1/README.md)
  (`WP4B-REAL-TARGET-PATH-METRIC-V1`).
- [E3] Eight Schools strict track, 12,830 / 10,346 ESS/s vs CmdStan,
  BlackJAX, NumPyro (walls on a loaded machine):
  [`STUDIES/eight_schools_v9_rebench_v1`](STUDIES/eight_schools_v9_rebench_v1/README.md)
  (`WP8-EIGHT-SCHOOLS-V9-REBENCH-V1`).
- [E4] posteriordb v3 (fresh seeds, WP24 default), 35/51 vs 37 and 31,
  0.34x per gradient, 0.75x wall per gradient, 1.35x nutpie ESS/s, gate wins
  on noncentered eight schools and `gp_pois_regr`:
  [`STUDIES/posteriordb_bench_v3`](STUDIES/posteriordb_bench_v3/README.md)
  (`WP25-POSTERIORDB-BENCH-V3`); v2 before the rule, with the frozen
  chains and the paper arm at 0.995x dual averaging:
  [`STUDIES/posteriordb_bench_v2`](STUDIES/posteriordb_bench_v2/README.md)
  (`WP23-POSTERIORDB-BENCH-V2`).
- [E10] the freeze mechanism (two-sided energy check at the initial leaf
  from overflow starts) and the `AcceptUnlessDivergent` warmup rule that
  unfroze 12/12 `arma11` chains:
  [`STUDIES/freeze_mode_v1`](STUDIES/freeze_mode_v1/README.md)
  (`WP24-FREEZE-MODE-V1`).
- [E5] Refinement on 1–3 % of retained transitions; kernel-side 0.7–0.8x:
  [`STUDIES/adaptation_parity_v1`](STUDIES/adaptation_parity_v1/README.md).
- [E6] U-turn rule 0.75x on the isotropic Gaussian, 1.0x correlated;
  `MomentumSum` 0.81x -> 1.09x; cache one gradient per transition:
  [`STUDIES/kernel_efficiency_v1`](STUDIES/kernel_efficiency_v1/README.md).
- [E12] `MomentumSum` on the 17 posteriordb models, fresh seeds, funnel at
  both tunings, Eight Schools strict track; preregistered default decision
  (not flipped): [`STUDIES/uturn_default_v1`](STUDIES/uturn_default_v1/README.md)
  (`WP26-UTURN-DEFAULT-V1`).
- [E13] The gap decomposed at CmdStan's step, metric and starts on six
  posteriordb models: leaves per orbit 0.60x under the endpoint U-turn
  statistic, gradients per leaf 1.01x, no selection difference;
  `MomentumSum` 0.77x -> 0.90x of reference NUTS per gradient:
  [`STUDIES/kernel_gap_v1`](STUDIES/kernel_gap_v1/README.md)
  (`WP30-KERNEL-GAP-V1`).
- [E7] Depth 10 ablation, 1.45x, 17/18 gates; `stan_style` 2.0x with
  regressions: [`STUDIES/adaptation_parity_v1`](STUDIES/adaptation_parity_v1/README.md).
- [E8] Appendix C on the funnel, 1.41x / 1.61x vs fixed paper tuning:
  [`STUDIES/paper_funnel_adaptive_v2`](STUDIES/paper_funnel_adaptive_v2/README.md)
  (`WP9-PAPER-H-RULE-STABILISATION-V2`).
- [E9] Appendix C v4 robust on the 14 freeze cells, geomean 1.04 vs dual
  averaging:
  [`STUDIES/paper_adaptation_robust_v1`](STUDIES/paper_adaptation_robust_v1/README.md).
- [E14] `MomentumSum` + Stan's regularisation together on the 17
  posteriordb models, fresh seeds, funnel at both tunings, Eight Schools
  strict track; preregistered joint default decision (1.51x, 41 vs 35
  cells, funnel and Eight Schools safe; not flipped on the per-model floor;
  flipped afterwards as a post-hoc decision):
  [`STUDIES/joint_default_v1`](STUDIES/joint_default_v1/README.md)
  (`WP31-JOINT-DEFAULT-V1`).
- [E15] posteriordb v5: the post-hoc default change validated on fresh
  seeds against rerun CmdStan and nutpie, five preregistered predictions
  held; 42/51 vs 36 and 28, 0.82x CmdStan per gradient on the healthy
  models (1.07x over 17), 0.80x wall per gradient, 1.40x / 3.09x ESS per
  second, funnel exact at the defaults:
  [`STUDIES/posteriordb_bench_v5`](STUDIES/posteriordb_bench_v5/README.md)
  (`WP32-POSTERIORDB-BENCH-V5`).
- [E16] Warmup restart-from-best chain rescue: 25/27 cells against the plain
  driver's 21, `lotka_volterra` 0/3 -> 3/3 and `arma11` 2/3 -> 3/3; the
  preregistered default rule held, with the mode-hiding caveat recorded:
  [`STUDIES/chain_rescue_v1`](STUDIES/chain_rescue_v1/README.md)
  (`WP33-CHAIN-RESCUE-V1`).
- [E17] posteriordb v6: complete then-current WP33 defaults on fresh seeds, 45/51
  gates against CmdStan 34 and nutpie 29, no frozen chain, 30 recorded
  rescues and funnel tail-mass |z| <= 2 on every seed; the release rule did
  not pass because one passing cell reached max |z| 4.023 and one `sblrc`
  process errored:
  [`STUDIES/posteriordb_bench_v6`](STUDIES/posteriordb_bench_v6/README.md)
  (`WP35-POSTERIORDB-BENCH-V6`).
- [E18] chain rescue v2: all 288 one-shot cells launched, 281 process-valid,
  with six heap-corruption exits and one post-result timeout leaving six
  invalid triplets. Two-hit reduced nuisance unique-chain actions 35 -> 14
  but failed its conjunctive gates. The rule then tested `current`, whose
  registered red lines were four origin-overwrite cells (five events) plus
  unknown HMM/92104 run history; only that second step selected `no_rescue`.
  The classifier found pathological/frozen ARMA and Lotka-Volterra origins
  and zero HMM origins, so WP36 does not establish genuine posterior-mode
  destruction:
  [`STUDIES/chain_rescue_v2`](STUDIES/chain_rescue_v2/README.md)
  (`WP36-CHAIN-RESCUE-V2`).
- [E11] The sampler defaults on the funnel: four levels 0.0203 / 0.0242 /
  0.0625 (z -3.5 / -3.8 / +0.3), eight levels 0.0412 / 0.0346 / 0.0897
  (|z| <= 1.43) at 1.05x / 1.00x ESS per call on Eight Schools and a 100-D
  Gaussian; lower `delta` alone makes the four-level bias worse:
  [`STUDIES/funnel_defaults_v1`](STUDIES/funnel_defaults_v1/README.md)
  (`WP28-FUNNEL-DEFAULTS-V1`).
- [E19] Dense metric: the old `Metric::dense()` warmup reused one RNG stream
  and installed a spurious ridge (0.08x the diagonal, 17/51 gates); fixed, it
  is 3.21x the diagonal per gradient over 17 posteriordb models with 40/51
  gates against 43/51 (`diamonds` 98.7x; `gp_pois_regr` 3/3 -> 0/3). The
  default change was an engineering decision on candidate-versus-old-dense
  evidence, not the frozen rule (which failed):
  [`STUDIES/dense_metric_posteriordb_v1`](STUDIES/dense_metric_posteriordb_v1/README.md)
  (`WP48-DENSE-METRIC-POSTERIORDB-V1`),
  [`STUDIES/dense_metric_confirmation_v1`](STUDIES/dense_metric_confirmation_v1/README.md)
  (`WP51-DENSE-METRIC-CONFIRMATION-V1`).
- [E20] Start rule: `Init::best_of(16)` met WP43's frozen rule (72 vs 71
  credited passes, 1.258x, no hidden mode) and the preregistered default-flip
  confirmation (1.254x, 42 vs 42 gates, funnel |z| <= 1.11, no two-mode hide
  event; the other 14 models 0.862x, one hidden-mode `hmm_drive_0` cell that
  `chain_warnings` named):
  [`STUDIES/init_rule_v1`](STUDIES/init_rule_v1/README.md)
  (`WP43-INIT-RULE-V1`),
  [`STUDIES/init_rule_confirmation_v1`](STUDIES/init_rule_confirmation_v1/README.md)
  (`WP52-INIT-RULE-CONFIRMATION-V1`).
- [E21] `RejectLeaf` as the sampler default: bit-identical on 73/73
  completed-abort cells, 75 vs 73 runs completed, the WP50 fatal sblrc seed
  rescued with every gate passing (max |z| 1.63); the rescue is in warmup and
  adds no divergence:
  [`STUDIES/nonfinite_policy_requalification_v1`](STUDIES/nonfinite_policy_requalification_v1/README.md)
  (`WP54-NONFINITE-POLICY-REQUALIFICATION-V1`).
- [E22] Chain-disagreement warnings: zero step/density false positives in 60
  screen cells, R-hat-check false positives only at R-hat 1.013 / 1.014,
  sensitivity resting on one wrong-chain cell:
  [`STUDIES/chain_disagreement_warning_v1`](STUDIES/chain_disagreement_warning_v1/README.md)
  (`WP44-CHAIN-DISAGREEMENT-WARNING`).
- [E23] Silent funnel: 11 of 12 wrong cells with zero retained divergences,
  all 12 failing the R-hat / ESS gates; the refined-leaf rate is not a
  usable warning:
  [`STUDIES/silent_funnel_diagnostic_v1`](STUDIES/silent_funnel_diagnostic_v1/README.md)
  (`WP55-SILENT-FUNNEL-DIAGNOSTIC`).
- [E24] Thread scaling: draws bit-identical across every thread count, the
  driver clamps threads to chains, wall tracks the longest chain (contended
  pilot):
  [`STUDIES/thread_scaling_v1`](STUDIES/thread_scaling_v1/README.md)
  (`WP45-THREAD-SCALING-V1`).
- [E25] Windows BridgeStan static runtime: 0/360 vs 2/120 faults and 3.2x /
  4.0x contended wall (WP50C); confirmatory gate not supported, 1/1000
  static (a sampler numerical error) vs 4/300 dynamic crashes (WP50D):
  [`STUDIES/bridgestan_windows_root_cause_v3`](STUDIES/bridgestan_windows_root_cause_v3/README.md)
  (`WP50C-BRIDGESTAN-WINDOWS-ROOT-CAUSE-V3`),
  [`STUDIES/bridgestan_windows_root_cause_v4`](STUDIES/bridgestan_windows_root_cause_v4/README.md)
  (`WP50D-BRIDGESTAN-WINDOWS-ROOT-CAUSE-V4`).
- [E26] posteriordb v7 at the post-WP51–54 defaults (`f097391c`): 43/51
  house cells against CmdStan 34 and nutpie 26, 6/15 on the five hard
  posteriors against 7 and 3, all 66 oWALNUTS cells completed, largest
  passing |z| 3.82, funnel z +1.69 / -0.59 / +0.84. ESS per gradient was
  0.708x CmdStan over the 15 complete fixed-16 models (v6 0.848), and the
  v6 release rule was not met. The descriptive dense arm passed 18/18 at
  13.4x the diagonal on the six correlated regressions (`diamonds` 67.5x):
  [`STUDIES/posteriordb_bench_v7`](STUDIES/posteriordb_bench_v7/README.md)
  (`WP56-POSTERIORDB-BENCH-V7`).
- [E27] Attribution of the v6 -> v7 per-gradient drop. Best-of-16 starts
  were 1.061x uniform paired on six models (gates 15/30 vs 18/30;
  `hmm_drive_0` second-mode chain on 2/5 seeds, named by `chain_warnings`),
  and reinstalled chain rescue was 1.023x; seed variation explains the
  rest:
  [`STUDIES/start_rule_paired_v1`](STUDIES/start_rule_paired_v1/README.md)
  (`WP60-START-RULE-PAIRED-V1`),
  [`STUDIES/rescue_removal_paired_v1`](STUDIES/rescue_removal_paired_v1/README.md)
  (`WP61-RESCUE-REMOVAL-PAIRED-V1`).
- [E28] v7 seed extension: three further fresh seeds on the fixed-16 set,
  oWALNUTS and CmdStan only. Per-gradient geomean 0.810 on the new seeds,
  0.761 pooled over six, leave-one-seed-out interval [0.740, 0.822]; gates
  40/48 new and 80/96 pooled against CmdStan 30/48 and 62/96; no passing
  cell above |z| 3.19. Recommends reporting the per-gradient figure with a
  seed interval over at least six seeds instead of gating a release on a
  three-seed value:
  [`STUDIES/posteriordb_bench_v7_seed_extension`](STUDIES/posteriordb_bench_v7_seed_extension/README.md)
  (`WP62-POSTERIORDB-V7-SEED-EXTENSION`).
- [E29] Funnel calibration at the defaults over 30 fresh seeds, arms default
  and `delta = 2` at 4 x 2,000/20,000 plus three arms at 1,000/1,000. Default
  mean z -0.419 (p 0.022), exceedance 4/30, pooled tail mass 0.0458; `delta
  = 2` 0/30 exceedances, mean z -0.408, 37 vs 43 divergences, 0.94x the
  default's funnel ESS per gradient; R2 passed, so `delta = 2` is a
  posteriordb confirmation candidate; no default changed:
  [`STUDIES/funnel_defaults_30seed_v1`](STUDIES/funnel_defaults_30seed_v1/README.md)
  (`WP53-FUNNEL-DEFAULTS-30SEED-V1`).
- [E30] BridgeStan dispatch on Linux (x86_64 glibc, GCC 13.3, BridgeStan
  2.9.0, 16 dedicated cores, pinned and co-tenanted): the default
  concurrent-replica dispatch is qualified: 0/500 child faults on every path,
  draws bit-identical to the serialised path on 16/16 fixed-16 models, 4.0–5.4x
  gradient throughput at four callers, wall per gradient 0.96x CmdStan's
  (one seed); serialising the calls costs 3.46x, which is where the Windows
  1.85x gap came from. `STAN_THREADS=true` is not free on Linux (1.57x per
  call on `arK`) and such a library is not unloaded on drop:
  [`STUDIES/bridgestan_linux_dispatch_v1`](STUDIES/bridgestan_linux_dispatch_v1/README.md)
  (WP65).
- [E31] Funnel tail deficit: at 30 fresh seeds the WP53 deficit did not
  replicate (default pooled 0.0465 ± 0.0017 against 0.0478, mean z -0.39);
  none of three mechanisms (step adaptation, refinement ceiling, U-turn rule)
  is supported and no setting is recommended; the default at 4 x 2,000/80,000
  over 30 seeds gives 0.0478 ± 0.0010, exactly the true value, so the
  residual was a low draw, not bias. Side finding: ten refinement levels cut
  funnel divergences 59 -> 1 with identical draws on the side targets:
  [`STUDIES/funnel_tail_deficit_v1`](STUDIES/funnel_tail_deficit_v1/README.md)
  (WP66) and the 80,000-draw arm of
  [`STUDIES/refinement_levels10_v1`](STUDIES/refinement_levels10_v1/README.md)
  (WP68).
- [E32] Trapped-chain restart (research flag
  `WarmupConfig::with_trapped_chain_restart`, default off): a chain whose
  step at the end of the first slow window is below 0.1x the chain median
  restarts from an independent best-of-16 start. On WP57's 12 `lotka_volterra`
  seeds it flagged exactly the two trapped chains (step ratios 0.0023 and
  0.025; lowest healthy 0.388), 0/48 trapped after restart, both cells passing
  with 2.4–4.6x fewer gradients; 0 false positives over 96 lotka and 72
  posteriordb chains; every unflagged run bit-identical to the defaults
  (42/42 pairs); the six-model regression arm identical (12/18 passes, ratio
  1.0000). Supported on two events; a confirmation study (WP69) runs before
  any default is proposed:
  [`STUDIES/trapped_chain_restart_v1`](STUDIES/trapped_chain_restart_v1/README.md)
  (WP67).
- [E33] Ten refinement levels as a default candidate (Cargo feature
  `candidate-levels10`, off): on the funnel at 30 seeds, divergences 268 -> 0,
  exhaustions 1,204 -> 1, tail mass unchanged (paired -0.0008 ± 0.0008), ESS
  per gradient 1.01x; on the 17 house posteriordb models x 3 seeds it is
  **not qualified**: 42 vs 44 passes and geomean ESS per gradient 0.824
  (the `hmm_drive_0` second-mode trap and three-seed noise; 1.007 excluding
  it, not preregistered). Eight levels stay; `max_refinement_levels(10)` is
  the funnel opt-in:
  [`STUDIES/refinement_levels10_v1`](STUDIES/refinement_levels10_v1/README.md)
  (WP68).
- [E34] posteriordb v7 and its seed extension re-run on Linux (x86_64 glibc,
  c7a.4xlarge, lane-pinned, co-tenanted) at the original commits, seeds,
  gates and analysis: oWALNUTS 44/51 house, 7/15 hard, 41/48 extension
  (Windows 43, 6, 40); CmdStan 33/51, 5/15, 31/48 (34, 7, 30); nutpie 27/51,
  5/15 (26, 3). 0/114 oWALNUTS cells bit-identical to Windows (start search
  identical in 114/114; divergence by warmup iteration 50). Six-seed
  per-gradient ratio vs CmdStan 1.206 (Windows 0.761), 0.862 excluding
  `hmm_drive_0` (Windows 0.749), where CmdStan is mode-trapped on 4/6 Linux
  seeds; wall per gradient 0.942 over the 15 complete models (Windows 1.849);
  ESS per second 1.215x CmdStan and 1.454x nutpie; dense arm 18/18 at 12.2x;
  funnel z +0.29, -0.53, +0.55:
  [`STUDIES/posteriordb_bench_v7_linux_v1`](STUDIES/posteriordb_bench_v7_linux_v1/README.md)
  (WP64).
- [E35] `accel_gp` gap (Linux, 3 fresh seeds, replicated dispatch vs
  CmdStan 2.39.0): 0.567x per gradient at the defaults, 0/3 gates for both
  samplers (CmdStan 37–174 divergences). None of three mechanisms met its
  criterion (reverse-check stops 55 % of orbits but median integration time
  0.87x CmdStan's; depth-cap stops 0.0001; metric mismatch 1.43x). No
  candidate qualifies: `target_accept 0.95` 0.616x (passes `accel_gp` 3/3,
  2.7x ESS at 2.5x gradients), `max_depth 12` 0.084x, warmup 2,000 0.192x.
  No default or flag changed:
  [`STUDIES/accel_gp_gap_v1`](STUDIES/accel_gp_gap_v1/README.md) (WP70).
- [E36] Trapped-chain restart confirmation (Linux, 261 cells, WP67's rule
  unchanged): **not proposed as a default**. On 60 fresh `lotka_volterra`
  seeds the defaults trapped 0/240 chains (about 1 in 252 over all fresh
  seeds, against 2/48 on WP57's targeted seeds) and the step rule fired on
  two chains that recovered on their own; on the 17 house models x 3 seeds
  it fired once on a passing `earnings` cell and missed a real `lotka` trap
  at step ratio 0.111 (cut 0.1); passes 42 = 42, ratio 1.0007, 50/50
  unflagged cells identical; 0 firings on 24 genuine second-mode cells;
  synchronisation cost +0.1 % / +1.2 % / +1.9 % at 1 / 4 / 16 chains. The
  chain-disagreement warning stayed silent on three 2-vs-2 mode splits that
  R-hat > 1.01 reported:
  [`STUDIES/trapped_chain_restart_confirmation_v1`](STUDIES/trapped_chain_restart_confirmation_v1/README.md)
  (WP69).
- [E37] nutpie's gradient-informed diagonal metric estimator as a research
  flag (`walnutpie::DiagonalMetricEstimator`, off; `s_i =
  sqrt(var(x_i)/var(g_i))` per slow window with the shipped regularisation),
  17 house models x 3 fresh seeds on Linux: **not supported**, geomean ESS
  per gradient 0.983 (0.844 without `hmm_drive_0`), passes 40 vs 43, 3 new
  divergences on centred Eight Schools; the overlapping-window variant 1.025
  and 38 passes; funnel 1.57x with divergences 9 -> 5 and P5 0.0480 ±
  0.0026; flag-off runs bit-identical and the fingerprint test passes:
  [`STUDIES/gradient_metric_v1`](STUDIES/gradient_metric_v1/README.md)
  (WP71).
- [E38] Per-gradient headline robustness: 12 further fresh Linux seeds of the
  fixed-16 set (oWALNUTS and CmdStan 2.39.0, 384 cells), analysed with
  WP64's six under four preregistered statistics: v7 pooled geomean 0.822
  [0.776, 0.892]; both-pass cells 0.870 [0.833, 0.891]; median of paired
  per-seed ratios **0.826 [0.789, 0.935]** (the statistic the frozen rule
  selects as the headline); without `hmm_drive_0` 0.824. CmdStan
  mode-trapped on `hmm_drive_0` in 5/18 cells (4/6 on WP64's seeds, 1/12
  on the new ones), oWALNUTS 1/18 and warned. Gates 239/288 vs 198/288.
  `one_comp` (CmdStan fails 18/18), `accel_gp` (0.48) and centred Eight
  Schools (0.39) move the headline most:
  [`STUDIES/posteriordb_ratio_robustness_v1`](STUDIES/posteriordb_ratio_robustness_v1/README.md)
  (WP72).
- [E39] Warmup gradient spend (Linux, 17 house models x 3 seeds): median
  warmup share oWALNUTS 0.524, CmdStan 0.508, nutpie 0.523, so spend is not
  the nutpie gap; the first 75 transitions cost 1.24x CmdStan per
  transition, slow windows 1.01x. Three research schedules all passed the
  frozen rule (gates not lower, ESS per total gradient >= 1.10, funnel
  exact): `init25` 43 gates / 1.44x but carried by `hmm_drive_0` (1.09x
  without it); **warmup 500** 40 gates / 1.32x, per-model median 1.25x and
  never below 1.21x leaving any model out, funnel P5 0.0499 ± 0.0032;
  `stablestop` (flag `WarmupConfig::with_stable_metric_stop`, off) 40 /
  1.12x. No default changed; WP77 is the fresh-seed confirmation:
  [`STUDIES/warmup_spend_v1`](STUDIES/warmup_spend_v1/README.md) (WP73).
- [E40] Chain-disagreement warning on mode splits (Linux): a
  pairwise-agreement-cluster rule K (when all-chain R-hat > 1.01, the
  largest group of chains whose pairwise R-hat <= 1.01 is the reference and
  every chain outside it is reported, provided the reference has at least
  two chains) reported 5/5 fresh two-mode splits (one 2-2, four 3-1) where
  the shipped leave-one-out check reported 1/5; 0 warnings added on 43 cells
  that pass every gate; 0/26 replayed WP44/WP55 warnings lost. Caveats: K
  misses a split where crossings leave no two chains agreeing (WP69 cell
  6903202; R-hat still flags it), and the shipped check itself fired on 3
  passing cells. **Shipped** as the added observe-only check
  `ChainWarning::RHatCluster`:
  [`STUDIES/chain_disagreement_splits_v1`](STUDIES/chain_disagreement_splits_v1/README.md)
  (WP74).
- [E41] Per-run dense / diagonal auto-selection (research flag
  `WarmupConfig::with_dense_auto_select`, off): dense iff the
  whitened-covariance condition-number ratio G = κ_diag / κ_dense >= 5 at
  the close of slow window 2, threshold fixed from WP48/WP51 records; 17
  house models x 3 seeds on Linux: 45/51 runs took the predicted branch,
  geomean ESS per gradient 2.30x the diagonal (dense arm 2.92x), funnel P5
  0.0480 ± 0.0034, flag-off bit-identical; **not proposed**: passes 39 vs
  the diagonal's 44 (gp_pois_regr 3 -> 1 on the dense branch, hmm_drive_0
  3 -> 1 and lotka_volterra / one_comp one seed each on the diagonal
  branch, which the dense driver ran rather than the diagonal path itself),
  and hmm_drive_0 0.09x; earnings chose diagonal on all seeds (in-run G
  0.02–1.5). WP79 fixes the diagonal branch and adds a GP guard:
  [`STUDIES/metric_autoselect_v1`](STUDIES/metric_autoselect_v1/README.md)
  (WP75).
- [E42] nutpie 0.16.8 on the fixed-16 x the same 18 Linux seeds (288 cells,
  one child process per seed; the oWALNUTS and CmdStan cells reused from
  WP64/WP72): gates oWALNUTS 239, CmdStan 198 (3 errors), nutpie 163 (7
  crashes, all `lotka_volterra`; non-centred Eight Schools 2/18, `diamonds`
  2/18, `hmm_drive_0` 11/18); median paired per-seed ratio oWALNUTS ÷
  nutpie: per gradient 0.699 [0.650, 0.962], per second 0.932 [0.865,
  1.275]; oWALNUTS ÷ CmdStan per second 0.886 [0.846, 1.000]. Stuck chains
  on `hmm_drive_0`: oWALNUTS 1/18, CmdStan 5/18, nutpie 6/18. nutpie was
  bit-identical to WP64 on all 45 cells both runs finished:
  [`STUDIES/nutpie_18seed_v1`](STUDIES/nutpie_18seed_v1/README.md) (WP76).
- [E43] Warmup schedule confirmation (Linux, 17 house models x 6 fresh seeds,
  funnel 30 seeds): **neither WP73 candidate confirms**. Warmup 500 fails the
  gate clause (81 vs 87) and the headline (1.119 [0.861, 1.224] per total
  gradient; 0.875x per sampling gradient; `hmm_drive_0` 0.356 and 3/6
  passes); initial phase 25 fails headline, median, leave-one-out, max |z|
  (5.85) and funnel (0.0530 ± 0.0051). Default warmup 1,000 and windows
  75/25/50 stay:
  [`STUDIES/warmup_schedule_confirmation_v1`](STUDIES/warmup_schedule_confirmation_v1/README.md)
  (WP77).
- [E44] Python call paths on Linux (lane-pinned, 3 seeds, gauss100 / Eight
  Schools / hier): wall per gradient at one thread, Rust target 1.57 / 0.57 /
  3.84 µs; `from_cfunc` 0.98–1.15x Rust; `from_pymc(gil_free=True)` 1.2–4.0x;
  plain numba callable 1.4–3.5x; default `from_pymc` 4–17x; `from_jax` 11–39x
  (about 20–40 µs extra per gradient). Compiled paths scale 3.4–3.8x at 4
  threads; callables and `from_jax` lose at 4 threads. `from_cfunc`, the
  Rust target and the numba callable gave bit-identical draws. The nutpie
  per-gradient gap persists on PyMC models (pooled 1.67x; Windows 1.70x);
  ESS per second `gil_free` 0.51–0.78x nutpie at 1 core and 0.53–1.21x at 4,
  `from_cfunc` 0.53–1.92x and 0.80–2.74x; nutpie failed non-centred Eight
  Schools 3/3, oWALNUTS passed 9/9 on every arm but `from_jax` (8/9):
  [`STUDIES/python_callpath_linux_v1`](STUDIES/python_callpath_linux_v1/README.md)
  (WP78).
- [E45] nutpie gap decomposition (18 seeds, 15 complete fixed-16 models, 24
  telemetry cells matching their WP72/WP76 cells 24/24): nutpie's
  per-gradient lead (×1.26 on the mean-of-logs scale, ×1.43 by per-model
  medians) is sampling gradients per retained draw (B = +0.58), not warmup
  (C = +0.03) and not ESS per draw, where oWALNUTS leads (A = −0.38). The
  consistent mechanism is a smaller effective step on every carrying model
  (sblrc raw step 0.10 vs 0.66; diamonds 0.0035 vs 0.062; on sblrc the
  installed inverse mass is about 11x the posterior variance on the betas
  against 1x on sigma); refinement spend matters on centred Eight Schools
  alone (30 % of transitions refined, 4.3 gradients per refined leaf):
  [`STUDIES/nutpie_gap_decomposition_v1`](STUDIES/nutpie_gap_decomposition_v1/README.md)
  (WP80).
- [E46] Metric auto-selection, round two (research flag, off): the diagonal
  branch is now the diagonal driver itself with a passive observer, and the
  run goes dense at window 2 only if a gradient-vs-position fit over windows
  1+2 is positive definite, its whitening gain is at least 5 and its worst
  coordinate R² at least 0.5 (bound set from WP75's recorded draws). 17
  house models x 3 fresh seeds on Linux: branch as predicted 45/51 (dense on
  diamonds, mesquite, nes2000, arK, hmm_example, lotka_volterra at 2.5–36.9x
  the diagonal; gp_pois_regr and accel_gp kept diagonal 6/6; earnings and
  kidiq went diagonal, their early windows not fitting a linear gradient
  model); **every rule held**: passes 44 vs 44, geomean 2.20x, no model
  below 0.9x, 0 new divergences, 43/43 diagonal-branch cells bit-identical
  to the default, funnel P5 0.0482 ± 0.0019, flag-off integrity. Proposed
  for a default-flip confirmation (WP85, E51: not qualified, branch choice
  seed-dependent on 3 of 22 models):
  [`STUDIES/metric_autoselect_v2`](STUDIES/metric_autoselect_v2/README.md)
  (WP79).
- [E47] `from_pymc(gil_free=True)` as a default (Linux, 10 PyMC model
  kinds x 3 seeds, 150 four-thread robustness runs): **not proposed**. It
  never errors where the default runs (the initval + `pm.Data` limitation
  raises `NotImplementedError` before sampling, pointing to
  `gil_free=False`), passes every gate the default passes, costs 0.13–0.46x
  the default's wall per gradient, 0/150 faults; but on 3 of 10 models
  (Data + dims + Deterministics 0/3, ar1 2/3, simplex 2/3) its draws did
  not reproduce those of the same compiled function run as a numba
  callable, all from the first process to compile each model; and the
  returned `CFuncTarget` is not callable as `target(q)`, so a flip would
  break the API. gil_free stays the documented opt-in:
  [`STUDIES/pymc_gil_free_default_v1`](STUDIES/pymc_gil_free_default_v1/README.md)
  (WP83).
- [E48] Centred Eight Schools refinement spend (Linux, 6 fresh seeds vs
  CmdStan 2.39.0): 71 % of refined transitions start in the lowest log-tau
  quartile (18x the top quartile's refined fraction); a quarter of
  transitions are refined and take 72 % of sampling gradients (184 per neck
  transition against CmdStan's 13 leapfrogs, where CmdStan shortens its
  trajectories at acceptance 0.48 and diverges on 11 % of those draws); the
  adapted step is 1.18x CmdStan's, so the step is set by the bulk; the
  default is 0.269x CmdStan per total gradient here. No candidate qualifies:
  cost-weighted acceptance statistic (research flag
  `DualAveragingAcceptance::CostWeightedCoarseEndpoint`, off) 0.577x and
  0.909 on the control set; Stan's acceptance statistic 0.929x but funnel
  0.0524 ± 0.0039 and control 0.618; two refinement levels 0.799x but 256 vs
  12 divergences and funnel 0.0075. Each beats the default 1.6–2.5x on the
  centred model alone and pays elsewhere:
  [`STUDIES/centered_eight_schools_refinement_v1`](STUDIES/centered_eight_schools_refinement_v1/README.md)
  (WP82).
- [E49] Diagonal metric shrinkage (Linux, house 17 x 3 seeds, 204 cells
  plus 30 funnel runs): the installed inverse mass is 0.9–1.1x the
  posterior variance on every model except sblrc (five coordinates at up to
  12.2x) and diamonds (one at 4.3x), so Stan's 1e-3 anchor explains the
  step gap only where it binds; nutpie's own metric sits below the variance
  (0.01–1.0x, all 66 accel_gp coordinates below 0.39x) yet its raw step is
  1.3–19x larger on all 17 models. Neither research regularisation
  (`DiagonalMetricRegularization::StanLowAnchor`, `StanCoordinateCap`,
  both off) meets the rule: 1.025x [0.997, 1.378] and 1.017x [0.990,
  1.422], per-model median 1.000, leave-one-model-out minimum 0.994 and
  0.982; each is bit-identical to the default on 27 of 51 cells, gains
  1.7–1.8x on sblrc and loses on earnings (0.73x / 0.88x). Gates 41 vs 40,
  funnel within one s.e., fingerprints held. `Stan` stays:
  [`STUDIES/diagonal_metric_shrinkage_v1`](STUDIES/diagonal_metric_shrinkage_v1/README.md)
  (WP81).
- [E50] `from_pymc(gil_free=True)` determinism (Linux, 5 PyMC models, 310
  processes alternating a purged and a warm numba cache): the wrapper is
  bit-identical to the PyTensor function it wraps in 310/310 processes
  (draws, and gradients at 50 probe points); threads 1 and 4 agree 60/60.
  The WP83 mismatches are PyTensor's own numba code under its default
  fastmath, which draws differently when compiled fresh than when loaded
  from numba's file cache (two hashes per affected model, one cold, one
  warm; the plain callable splits the same way). Fastmath off or the file
  cache off each give one hash per model at unchanged wall per gradient.
  Fixed: gil_free now compiles under `numba__fastmath=False`:
  [`STUDIES/pymc_gil_free_determinism_v1`](STUDIES/pymc_gil_free_determinism_v1/README.md)
  (WP86).
- [E51] Hessian-fit dense auto-selection as the default (Linux, 22 v7
  posteriors x 6 fresh seeds x {diagonal, auto} at 4 x 1,000/1,000, funnel
  30 seeds): **not qualified**. Passes 105 vs 105, headline 2.01x the
  diagonal, no model below 0.9x, 0 new divergences, 122/122 diagonal-branch
  cells bit-identical to the default, funnel P5 0.0492 ± 0.0017, 0
  lotka_volterra trapped cells; but the branch choice was the same on all
  six seeds for only 19 of 22 models against the required 20 (kidiq dense
  on 4/6, garch11 2/6, lotka_volterra 4/6, each near the linearity bound or
  the gain threshold; both branches pass every gate there). Observer cost
  1.026x wall per gradient on diagonal-branch models; dense-branch warmup
  used 0.49x the diagonal's warmup gradients. Above 256 dimensions the flag
  is now the plain diagonal run (radon, grsm_irt). The flag stays research
  opt-in:
  [`STUDIES/metric_autoselect_confirmation_v1`](STUDIES/metric_autoselect_confirmation_v1/README.md)
  (WP85).
- [E52] Online stochastic-volatility quote benchmark (Linux, 4 pinned
  cores, simulated t5 / AR(1) log-vol data, one return per tick for 100
  ticks, N = 250 and 1,000, 3 seeds, 32 cells): a warm continuation
  (each chain's last position, step and diagonal metric carried over, the
  new latent appended, 50 or 200 transitions per chain, built in the study
  harness because the session API cannot be retargeted) refreshes the
  posterior in 20 ms / 80 ms median at N = 250 (0.27 s / 1.07 s at
  N = 1,000) against 1.1 s for a nutpie refit, 3.1 s for an oWALNUTS refit
  and 6.5 s for CmdStan (4.5 s / 16.7 s / 42 s at N = 1,000); it stayed
  calibrated over 100 ticks (90.1–90.3 % of warm draws inside the
  reference 90 % interval, early-vs-late drift at most 0.003, 6/6 runs;
  coverage of the true log-vol 85–87 % against 87–90 % for refits; 0
  divergences anywhere). The frozen accuracy bar (R-hat ≤ 1.01 and
  quantiles within 3 reference MCSE) is met on 0–2 % of warm ticks and
  9–14 % of refit ticks, so "real-time" is not claimed; the N = 1,000
  reference (4 x 22,000 draws x 1,004 dimensions) failed every tick at the
  result-size limit and was not rerun:
  [`STUDIES/online_sv_quote_v1`](STUDIES/online_sv_quote_v1/README.md)
  (WP84). A post-hoc, non-preregistered rescoring
  ([`posthoc/README.md`](STUDIES/online_sv_quote_v1/posthoc/README.md))
  against the quote itself: the 200-draw warm refresh keeps the P50 of
  next-period sigma within 2 % and the P95 within 5 % of the reference on
  97 % / 98 % of ticks (median 0.64 % / 1.27 %, no drift), the 50-draw
  refresh on 74 % / 78 %; the reference floor is 0.08–0.3 % MCSE. As
  sampled, the oWALNUTS and CmdStan full refits are *worse* than the
  200-draw warm refresh at those tolerances because of stuck chains on
  7 % / 13 % of ticks (nutpie 0 %), each named by the chain warnings;
  the reference itself had a frozen chain on 4 of 100 ticks.
- [E53] Why one chain freezes in warmup on the WP84 SV model (Linux, 120
  fresh seeds x {oWALNUTS, CmdStan, nutpie} at 4 x 1,000/1,000, 9
  mechanism arms x 60 seeds, 3 candidates on the same 120 seeds, funnel 30
  seeds, 3 house models; 1,416 cells): trapped chains per 480 are nutpie
  0, oWALNUTS 8, CmdStan 17. Every trap starts at log_sigma above 1.3 (max
  |gradient| 2.5e7 against 1.5e3 at the mode), its first transitions are
  rejected, the identity-metric step collapses below 1e-4 by transition 6,
  and the first metric update at transition 99 installs the Stan
  regularisation floor on every coordinate, locking the chain 1,000–4,300
  nats below the mode at 4.7x the warmup gradients; the chain warnings
  name all 8 with no false positive. nutpie escapes through its
  gradient-scaled initial metric alone (1/240 with oWALNUTS's starts);
  step search, estimator and window schedule do not help. The WP67 restart
  rule at ratio 0.01 instead of 0.1 (`guard-0.01-0`) takes 8/480 to 0/480
  with 110/110 unfired cells bit-identical, no firing on the funnel or the
  house models and no cost; proposed for a default-flip confirmation, not
  flipped. Research `TrappedChainRestartConfig::with_check_window` added:
  [`STUDIES/sv_stuck_chains_v1`](STUDIES/sv_stuck_chains_v1/README.md)
  (WP89).
- [E54] Trapped-chain guard default-flip confirmation (Linux, 22 v7
  posteriors x 6 fresh seeds x {defaults, guard} at 4 x 1,000/1,000,
  funnel 30 seeds, the SV model at 120 fresh seeds): **qualifies on every
  rule**. Passes 92 = 92, 282/282 cell pairs bit-identical where the guard
  did not fire (268 cells) or on the untouched chains (14 fired cells), no
  new divergences, headline ESS per gradient 1.000 [1.0, 1.0], funnel P5
  0.0458 ± 0.0016 with 0 firings, SV trapped chains 0/480 against the
  defaults' 8/480 (13 firings: the 8 traps and 5 near-traps). On the
  posteriordb set it fired twice in 1,056 chains, both on kilpisjarvi at
  step ratios 0.009 and 0.006; each restarted chain ended at the mode, and
  both cells fail their gates in both arms on other chains. Caveat: at the
  defaults those two chains would have recovered on their own, so on this
  3-D model the rule fired on a slow start rather than a trap, at no cost.
  Applied as the default (ratio 0.01, first slow window; draws change only
  on fired chains; `ALGORITHM_REVISION` and fingerprints unchanged):
  [`STUDIES/trap_guard_confirmation_v1`](STUDIES/trap_guard_confirmation_v1/README.md)
  (WP90).
- [E55] Online SV quote benchmark v2 on the library warm API (Linux, 3
  parallel lanes, 58 cells in 95 minutes; simulated series at N = 250 and
  1,000 and the archived real BTC-perpetual 30-minute bar-close returns at
  N = 250; 3 seeds; gated 4 x 2,000/20,000 reference on 173 ticks, 1 of
  which needed its second seed): at K = 200 transitions per chain the warm
  refresh keeps the next-period sigma P50 within 2 % and P95 within 5 %
  of the reference on 96.7 % of ticks at both simulated sizes (median 78 ms
  at N = 250, 1.06 s at N = 1,000, 100 % under the 2 s threshold) and
  **passes the frozen rule there**, but on the real series on 83.3 % of
  ticks (two seeds below 90 %, median 309 ms), so no "real-time quote
  refresh" sentence is made. Latency never bound: the pass rate tracks
  the arm's own P50 MCSE (0.9 % simulated, 1.25 % real at K = 200; K = 100
  60–83 %, K = 50 39–58 %). All 27 warm cells calibrated (0.896–0.907 of
  draws inside the reference 90 % interval), no stuck chain or divergence,
  no drift with a common sign. Baselines: nutpie refits 100 % accurate at
  0.9–4.2 s; oWALNUTS and CmdStan refits 90–97 % as sampled because of
  stuck chains (every oWALNUTS one flagged; gated 100 %). Python
  `sample_warm` on a C-ABI target: 71 ms against 77 ms for the Rust cell:
  [`STUDIES/online_sv_quote_v2`](STUDIES/online_sv_quote_v2/README.md)
  (WP88).
- [E56] Tick-amortised accuracy (Linux, WP84 series at N = 250, 100 ticks,
  3 seeds, gated reference at every tick, 17 cells in 37 minutes): pooling
  the last H ticks' warm draws as they stand does not let K fall below
  200. The reference posterior's own sigma P50 moves 3.4 % per tick
  (median; 9–16 % over 5–20 ticks) against a 2 % tolerance, so every
  pooled configuration fails (10–32 % of ticks, nearly independent of K,
  exponential weights beating uniform on 15/15 pairs) and only K = 200
  without pooling passes (95.0 %, 78 ms); re-propagating stale draws with
  fresh noise biases the P95 high. Post hoc, not preregistered: a
  likelihood-reweighted pool with weights normalised within each lag puts
  K = 20 with H = 20 at 95.0–95.3 % (7.9 ms per tick) and K = 50 at
  95.7–97.3 % for H of 5 to 20; to be confirmed with the real series:
  [`STUDIES/tick_pooling_v1`](STUDIES/tick_pooling_v1/README.md)
  (WP93).
- [E57] nutpie's gradient-scaled initial metric as a default (Linux, 22 v7
  posteriors x 6 fresh seeds x {defaults, with the initial metric, with it
  and the guard off}, funnel 30 seeds, SV model 120 seeds; 906 cells in
  68 minutes): **not qualified**. Headline ESS per gradient 1.15x geomean
  (paired median 1.08 [1.04, 1.14]; accel_gp 2.98x, radon 2.11x, centred
  Eight Schools 1.63x) but passes 96 against 101, warmup gradients 0.87x
  with gates lost on six models (hmm_drive_0 6 to 4, one_comp, mesquite,
  gp_pois_regr, lotka_volterra, seeds), no new divergences, funnel P5
  within 1 s.e. On the SV model the cause-level fix removes 11 of the
  guard's 15 firings and halves warmup gradients, but 4/480 chains still
  trap without the guard (the rule asked for at most 1). On lotka_volterra
  it lifts a stuck chain's step above the guard's 1 % cut without freeing
  it, so the guard no longer fires there. A start gradient far from the
  typical set is not a scale (initial masses of 1e5–1e8 on three models).
  The flag stays research; the next candidate is a bounded variant with a
  guard signal that survives a scaled metric:
  [`STUDIES/grad_init_metric_v1`](STUDIES/grad_init_metric_v1/README.md)
  (WP94).
