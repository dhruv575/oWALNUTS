# Kernel efficiency v1 — where the per-gradient gap to NUTS goes

Status: exploratory instrumentation study, executed 2026-09-02 on branch
`wt/kernel-efficiency`. Not preregistered (it produces the candidates for a
preregistered posteriordb rerun; it flips no default). Harness:
`examples/kernel_efficiency.rs` (targets, instrumentation, reference NUTS)
and `examples/funnel_kernel_options.rs` (funnel tail-mass check).
Artifacts: `artifacts/kernel_efficiency.json` (every cell),
`artifacts/summary.json` and `artifacts/results-table.md` (seed medians,
from `analyze.py`), `artifacts/run.log`, `artifacts/funnel-*.log`.

## Question

After matching Stan's warmup and depth (`STUDIES/adaptation_parity_v1`),
oWALNUTS still gets 0.7–0.8x CmdStan's minimum bulk ESS per gradient on the
easy posteriordb models where refinement is never engaged, i.e. while it is
running as NUTS. Which kernel-side difference costs what?

## Protocol

Three hand-written Rust targets: noncentered Eight Schools (10-D),
a 100-D standard Gaussian, and a 50-D correlated Gaussian
(`Sigma^-1 = R diag(lambda) R'`, `lambda` log-spaced over `[1, 100]`,
`R` a fixed Haar rotation, so no diagonal metric whitens it). Four chains,
three seeds. Per seed, the default oWALNUTS warmup (`h0 = 0.1`, depth 10,
four refinement levels, `delta = 1`, dual averaging at 0.8, adapted diagonal,
1,000 transitions) runs once per chain and hands its final step, metric and
last state to every arm, which then samples 1,000 transitions with a fixed
kernel. Warmup is therefore identical across arms and only the kernel differs.

Metric: minimum over coordinates of bulk ESS (`owalnuts::diagnostics::ess_bulk`,
ArviZ's estimator) over the 4,000 retained draws, divided by the sampling
gradients (target evaluations). Seed medians; the three seeds are listed in
`results-table.md`, their spread is ±10 % on the minimum-ESS statistic.

Arms (all with the same adapted `h` and metric, depth 10):

| arm | what it is |
|---|---|
| `nuts-ref` | clean-room reference NUTS in the harness (~250 lines): Stan's `base_nuts` — multinomial sampling within subtrees, biased progressive sampling across doublings, generalised no-U-turn criterion `p_sharp . rho` on the summed momenta with the 2.21+ cross checks, divergence at `H - H0 > 1000` |
| `default` | oWALNUTS `v10` kernel: `delta = 1`, four levels, endpoint U-turn rule, orbit ends on refinement exhaustion |
| `default+cache` | same kernel, `RunConfig::with_cached_initial_evaluation(true)` |
| `delta1000` | `delta = 1000` (the `ramp` value of the adaptation study: refinement never engages) |
| `exhaust-accept` | `ExhaustionRule::AcceptBelowDivergenceThreshold` (ablation i: Stan's rule for a leaf over `delta` at every level) |
| `cross` | `UTurnRule::EndpointsWithCross` (ablation ii: Stan's cross checks, endpoint statistic) |
| `rhosum` | `UTurnRule::MomentumSum` (ablation ii: Stan's statistic and cross checks) |
| `levels1-accept` | one refinement level + accept rule = NUTS with the endpoint U-turn rule inside the oWALNUTS machinery |
| `levels1-accept+rhosum` | one level + accept + momentum sum = NUTS inside oWALNUTS; control for the reference implementation |
| `…+cache` | the same with the initial-evaluation cache |

Ablation (iii), the outer selection, needs no arm: `combine_barker` (within
subtrees) is already exact multinomial and `combine_metropolis` (across
doublings) is already biased progressive, exactly Stan's pair;
`STUDIES/outer_selection_bps_vs_multinomial_v1` showed the biased join is
1.75x the multinomial one, so there is nothing to gain there.

Ablation (iv), skipping the reverse check for single-micro-step leaves, is
provably a no-op and gets a test instead of an arm: the reverse coarsening
loop runs `while coarse_steps / 2 >= min_micro_steps`, so a leaf accepted at
level 0 with `min_micro_steps = 1` never integrates backwards
(`reverse_evaluations == 0`, asserted by
`default_kernel_options_are_the_frozen_rules`). The reverse check is paid only
by leaves that refined, and those are 0–6 % of leaves here.

## Results

Seed medians of minimum bulk ESS per gradient (x1e3). "with cache" is the
same draws divided by the gradient count without the per-transition
re-evaluation (exact, since the cache does not change a single draw; the
`default+cache` arm ran it and reports `draws_identical_to_default: true` on
every cell).

| arm | Eight Schools | with cache | 100-D Gaussian | with cache | 50-D correlated | with cache |
|---|---:|---:|---:|---:|---:|---:|
| `nuts-ref` | **73.5** (1.00x) | 73.5 | **115.6** (1.00x) | 115.6 | **22.5** (1.00x) | 22.5 |
| `default` | 59.2 (0.81x) | 66.6 (0.91x) | 86.3 (0.75x) | 93.6 (0.81x) | 23.1 (1.03x) | 23.9 (1.06x) |
| `delta1000` | 61.9 (0.84x) | 70.0 (0.95x) | 86.3 (0.75x) | 93.6 (0.81x) | 22.7 (1.01x) | 23.4 (1.04x) |
| `exhaust-accept` | 59.2 (0.81x) | 66.6 (0.91x) | 86.3 (0.75x) | 93.6 (0.81x) | 23.1 (1.03x) | 23.9 (1.06x) |
| `cross` | 54.5 (0.74x) | 61.3 (0.83x) | 112.6 (0.97x) | 126.7 (1.10x) | 23.5 (1.04x) | 24.3 (1.08x) |
| `rhosum` | 56.5 (0.77x) | 63.5 (0.86x) | 112.7 (0.97x) | 126.4 (1.09x) | 23.3 (1.03x) | 24.0 (1.07x) |
| `exhaust-accept+rhosum` | 56.5 (0.77x) | 63.5 (0.86x) | 112.7 (0.97x) | 126.4 (1.09x) | 23.3 (1.03x) | 24.0 (1.07x) |
| `levels1-accept` | 61.9 (0.84x) | 70.0 (0.95x) | 86.3 (0.75x) | 93.6 (0.81x) | 22.7 (1.01x) | 23.4 (1.04x) |
| `levels1-accept+rhosum` | 66.5 (0.91x) | 74.7 (1.02x) | 115.4 (1.00x) | 129.5 (1.12x) | 21.6 (0.96x) | 22.2 (0.99x) |

Per-transition instrumentation (seed medians; "non-leaf" = target
evaluations that did not build a leaf: the initial re-evaluation, refinement
attempts, reverse checks, rejected leaves):

| target | arm | grad/transition | leaves/transition | non-leaf grad/tr | of which initial re-eval | depth | refined orbits | orbit ended by |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Eight Schools | `nuts-ref` | 8.1 | 8.1 | 0.00 | 0 | 3.06 | — | U-turn 99.9 %, divergence 0.1 % |
| | `default` | 9.0 | 7.3 | 1.71 | 1.00 | 3.00 | 5.9 % | outer U-turn 79 %, recursive U-turn 10 %, reverse-coarser rejection 11 %, exhaustion 0 % |
| | `rhosum` | 9.4 | 7.7 | 1.72 | 1.00 | 3.07 | 5.7 % | outer 82 %, recursive 7 %, reverse-coarser 11 % |
| | `levels1-accept+rhosum` | 9.2 | 8.2 | 1.00 | 1.00 | 3.13 | 0 | U-turn 100 % |
| 100-D Gaussian | `nuts-ref` | 8.3 | 8.3 | 0.00 | 0 | 3.13 | — | U-turn 100 % |
| | `default` | 12.8 | 11.8 | 1.00 | 1.00 | 3.33 | 0 | outer 86 %, recursive 14 % |
| | `rhosum` | 9.4 | 8.4 | 1.00 | 1.00 | 3.17 | 0 | outer 92 %, recursive 8 % |
| 50-D correlated | `nuts-ref` | 33.8 | 33.8 | 0.00 | 0 | 4.95 | — | U-turn 100 % |
| | `default` | 31.8 | 30.6 | 1.12 | 1.00 | 4.94 | 1.1 % | outer 87 %, recursive 11 %, reverse-coarser 1.4 % |
| | `rhosum` | 34.5 | 33.3 | 1.13 | 1.00 | 5.05 | 1.2 % | outer 87 %, recursive 11 %, reverse-coarser 1.3 % |

No arm had a depth-cap stop or a divergence on any target except the
reference's 0.1 % divergences on Eight Schools (a leaf with `H - H0 > 1000`
in the `tau -> 0` corner; oWALNUTS refines through the same leaves).

## What explains the gap

1. **The `sample_chains` path re-evaluates the current state at the start of
   every transition** (`target_calls_initial` = 1 per transition). The kernel
   has an exact cached-input path (`transition_w_from_evaluated…`) but the
   facade only used it for structured-refresh runs
   (`use_persistent_cache = persistent.is_some()` in `run_chain`). Stan never
   pays this call. It is a flat 1 gradient per transition: 11 % of the
   gradient count on Eight Schools and the 100-D Gaussian (8–9 leaves per
   orbit), 3 % on the correlated Gaussian (34 leaves). This is the one
   mechanism that is target-independent and applies to every posteriordb
   model at similar depth. Opt-in fix: `RunConfig::with_cached_initial_evaluation`
   / `Sampler::cache_initial_evaluation`; the draws are bit-identical (the
   fingerprint tests hash the call count, hence opt-in).

2. **The endpoint U-turn statistic builds longer orbits than Stan's momentum
   sum on isotropic targets.** oWALNUTS tests `rho_end . M^-1 (q_end - q_start)`
   at the two extremes of the merged span; Stan tests `(M^-1 p_extreme) . rho`
   with `rho` the sum of all leaf momenta, at both extremes and across the two
   subtree boundaries. The two differ by the boundary half-momenta and by the
   cross checks. On the 100-D Gaussian the endpoint rule stops 3.4 leaves
   later per orbit (11.8 vs 8.4) for no ESS gain: the extra leaves are the
   tail of a trajectory that has already turned in the momentum-sum sense.
   Switching to `MomentumSum` (or just adding the cross checks, `cross`)
   recovers reference parity there: 0.81x -> 1.09x with the cache. On the
   correlated Gaussian the two rules are within seed noise (1.04–1.08x), and
   on Eight Schools `rhosum` is 0.86x vs `default` 0.91x (with cache), a
   difference inside the ±10 % seed spread. So the U-turn rule is worth
   0–35 % depending on the geometry and never costs more than noise.

3. **Refinement itself costs 4–15 % where it engages, through
   reverse-coarser rejections, not through reverse-check gradients.** On
   Eight Schools 6 % of orbits select a refined leaf and 11 % of orbits *end*
   because a refined leaf was rejected by the reverse coarsening test
   (`ReverseCoarserAccepted`: the reverse trajectory from the refined endpoint
   passes at a coarser level, so the leaf is not reversible and the orbit
   stops there). The non-leaf gradient cost is 0.7 per transition with the
   cache (refinement attempts plus reverse checks), and `delta = 1000`
   (no refinement) or one level (`levels1-accept`) gains 5 % over `default`;
   with the momentum sum the same comparison (`rhosum` vs
   `levels1-accept+rhosum`) is 15 %. On the Gaussians refinement never engages
   and costs nothing.

4. **`delta = 1` never ends an orbit on these targets** (ablation i). With
   four levels not a single leaf exhausted refinement in 36,000 orbits, so
   `exhaust-accept` is bit-identical to `default` here; `delta1000` differs
   only by not refining. The exhaustion rule matters where the adaptation
   study saw chains freeze (uniform(-2, 2) starts in a tail with `|dH| > 1` at
   every level); it is a robustness option, not a per-gradient one.

5. **Selection is not a factor** (ablation iii): the within-subtree and
   across-doubling joins already are Stan's pair.

6. **The reverse check is not a factor for unrefined leaves** (ablation iv,
   no-op by construction).

Control: `levels1-accept+rhosum` — one level, Stan's exhaustion rule, Stan's
U-turn rule, oWALNUTS's selection — is the reference NUTS re-expressed in the
oWALNUTS machinery and lands at 0.91x / 1.00x / 0.96x of the reference without
the cache and 1.02x / 1.12x / 0.99x with it, i.e. at parity within seed noise.
This validates the reference implementation and shows that the remaining
per-gradient difference between oWALNUTS and NUTS on these targets is the
sum of the three mechanisms above.

Accounting for the posteriordb 0.7–0.8x: the re-evaluation alone is 0.9x at
depth 3 (8 leaves) and 0.97x at depth 5; the U-turn rule is 0.75x on the
isotropic Gaussian and 1.0x on the correlated one; refinement rejections are
0.85–0.95x where refinement engages (Eight Schools 6 %, posteriordb models
1–3 %). Their product spans 0.65–0.95x, consistent with the observed
0.7–0.8x. The largest single contribution on a given posteriordb model is
expected to be the U-turn rule where the adapted metric makes the posterior
nearly isotropic (arK, garch11, mesquite) and the re-evaluation elsewhere.

## Funnel check

`examples/funnel_kernel_options.rs` runs the `funnel_paper_adaptation`
protocol (Appendix C warmup, identity metric, `h = 0.1`, `delta = 1`, eight
levels, depth 10, 4 x 2,000 / 20,000, seed `0x0f0f2026`) under the candidate
options. Exact `P(omega < -5) = 0.0478`.

| options | estimate | batch-means s.e. | z | target calls | depth caps / divergences |
|---|---:|---:|---:|---:|---|
| default (`Endpoints`, `Stop`, no cache) | 0.0436 | 0.0066 | -0.64 | 2,218,854 | 6 / 0 |
| `MomentumSum` | 0.0456 | 0.0051 | -0.43 | 2,528,799 | 2 / 0 |
| `MomentumSum` + cache | 0.0456 | 0.0051 | -0.43 | 2,440,803 | 2 / 0 |
| `MomentumSum` + `AcceptBelowDivergenceThreshold` + cache | 0.0456 | 0.0051 | -0.43 | 2,440,803 | 2 / 0 |

The tail mass is preserved under every candidate (|z| < 1). The cache saves
exactly 88,000 calls (one per transition, 4 x 22,000) with identical draws.
The exhaustion rule never triggers on the funnel at eight levels (identical
draws and call count to `MomentumSum` + cache), so it neither helps nor harms
there. The momentum-sum rule uses 14 % more calls on the funnel than the
endpoint rule (longer orbits in the neck, where the adapted `delta` is 1.2–1.3)
at a smaller tail-mass s.e.; per call the two are within noise of each other
(this run has one seed and is a bias check, not an efficiency measurement).

## Recommendation for the preregistered posteriordb study

Candidates for the next `sampler` default, to be decided by a preregistered
rerun of `STUDIES/posteriordb_bench_v1` (not flipped here):

1. `Sampler::cache_initial_evaluation(true)`: draws bit-identical, one gradient
   per transition saved, no possible downside. Should become the default; it
   is opt-in only because the frozen fingerprints hash the call count.
2. `KernelOptions { u_turn: UTurnRule::MomentumSum, .. }`: Stan's criterion.
   Parity with NUTS on the isotropic Gaussian (+35 %), neutral within noise on
   the correlated Gaussian and Eight Schools, funnel tail mass preserved. The
   preregistration should gate on "no model below 0.9x the endpoint rule
   beyond seed noise", as in `adaptation_parity_v1`.
3. `ExhaustionRule::AcceptBelowDivergenceThreshold`: no effect on any target
   here; recommended as an additional arm because it removes the tail-freeze
   mechanism of the adaptation study (a downhill leaf with `|dH| > delta` at
   every level no longer ends the orbit) and is what makes
   `WarmupConfig::stan_style` safe without the `delta` ramp. It should be
   tested with the same R-hat gate.

Not recommended: `delta = 1000` or one refinement level as defaults (they
are NUTS and forfeit the funnel result); `EndpointsWithCross` (same gain as
`MomentumSum` on the Gaussian, worse on Eight Schools, and not Stan's rule).

## Implementation notes

* `walnutpie::KernelOptions` is a new field of `FixedTuning` /
  `KernelTuning` (`with_options`) and `sampler::Tuning::kernel_options`.
  `UTurnRule::MomentumSum` keeps a `rho_sum` vector per `Span` (one
  `dimension`-length allocation per leaf, empty under the other rules); each
  macro leaf contributes its endpoint momentum, so with one micro-step the sum
  is exactly Stan's. The cross checks reuse the span endpoints
  (`earlier.forward`, `later.backward`), so `EndpointsWithCross` needs no
  extra storage.
* `ExhaustionRule::AcceptBelowDivergenceThreshold` accepts the finest attempt
  when its endpoint error is at most `divergence_threshold` and then runs the
  ordinary reverse coarsening check; since the finest reverse level is the
  exact time reversal (same error) and every coarser reverse level must fail
  `delta`, the reverse leaf selects the same level by the same exhaustion —
  `exhaustion_accept_keeps_the_finest_leaf_below_the_divergence_threshold`
  asserts the round trip.
* Defaults are untouched: `KernelOptions::default()` and the cache off take
  exactly the `v10` code paths; `tests/kernel_fingerprint.rs` and the full
  suites pass with and without `research`.

## Deviations and caveats

* Single machine, walls not recorded (the harness measures gradients only).
* Three seeds; the minimum-ESS statistic has ±10 % seed spread, so
  differences under ~15 % on one target are not resolved. The 100-D Gaussian
  U-turn effect (0.81x -> 1.09x) and the re-evaluation cost (exact) are well
  outside it; the Eight Schools `rhosum` vs `default` comparison is not.
* The reference NUTS uses its own RNG stream; it is validated by the
  `levels1-accept+rhosum` control, not by bit comparison.
* The funnel check is one seed and shares the adapted `delta`/`h` between
  the momentum-sum runs only by construction (same warmup RNG path); it is a
  bias gate, not an efficiency comparison.

## Reproduce

```
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu cargo run --release --example kernel_efficiency -- --seeds 3 --draws 1000 --warmup 1000 --out STUDIES/kernel_efficiency_v1/artifacts
python STUDIES/kernel_efficiency_v1/analyze.py
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu cargo run --release --example funnel_kernel_options -- --uturn rhosum --cache
```

The harness is deterministic in its draws given the seeds (~20 s for the
three targets; the funnel check ~1 min per configuration).
