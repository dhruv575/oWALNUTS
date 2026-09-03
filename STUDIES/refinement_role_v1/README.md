# refinement_role_v1 (WP34) — does WALNUTS's own mechanism pay off on ordinary posteriors?

Preregistered in `PREREGISTRATION.md` / `protocol.json`, frozen after the
phase-1 instrumentation and before the first phase-2 cell. Seeds 89101-89103,
17 posteriordb posteriors, 8 arms, 4 chains x 1,000/1,000, `posteriordb_bench_v5`
protocol verbatim; CmdStan cited from v5. 408 cells, all present.

## Question

`posteriordb_bench_v5` left oWALNUTS at 0.67-0.95x CmdStan's minimum bulk ESS
per gradient on every healthy model. The JMLR paper's promise is the opposite:
refinement does the local work, so the macro step `h` should be able to run
**larger** than a NUTS step, and the rare refined leaf should be repaid by
fewer leaves per orbit elsewhere. Is that promise realisable here?

## Answer: no, and the instrumentation says why

**1. The adapted macro step already *is* Stan's step.** Geometric mean of the
per-model ratio of oWALNUTS's adapted `h` to CmdStan's adapted step: **1.000**
(0.79-1.23 across models, 0.87-1.12 on the fourteen healthy ones). Dual
averaging at 0.8 on the coarse-endpoint statistic lands on the NUTS step, so
there is no headroom being left on the table by the adapter.

**2. Refinement almost never engages.** Median fraction of retained built
leaves accepted above level 0: **0.22%** (0.00%-3.3%). Gradients per built
leaf 1.00-1.09.

**3. There is no stiff subpopulation for refinement to absorb.** The level-0
leaf-error trace (fresh momenta, one macro step at multiples of the adapted
`h`) shows a single smooth population: the ratio q99/q50 of `|dH|` at `h` is
about 10 on every healthy model. Raising the step moves the *whole*
distribution, not a tail: `P(|dH| > 1)` goes 0.4-6% at `h`, 12-27% at 1.5h,
28-62% at 2h, 60-97% at 3h. Once a third to a half of leaves refine, the
reverse-coarser stop ends most transitions. A level-1 leaf at 2h costs the
same two gradients as two level-0 leaves at h, plus its reverse check, so
there is nothing to win.

**4. Empirically, larger steps lose.** Every arm that raises `h` (dual
averaging at 0.6, Appendix C at Gamma 0.6) is worse per gradient, exactly as
the trace predicts.

**5. Where oWALNUTS is furthest behind CmdStan, the cause is refinement's own
reverse-coarser stop, not the step.** The fraction of retained transitions
ending in a reverse-coarser stop is 0.8-7% on the regressions but **10%** on
the noncentered eight schools, **20%** on `gp_pois_regr`, **21%** on the
centered eight schools and **54%** on `accel_gp` - the four models with the
worst per-gradient ratios in v5 (0.75, 0.75, -, 0.47x).

## Arms (seed medians; ratios of minimum bulk ESS per gradient)

| arm | rule | vs `da` (17) | vs `da` (healthy) | vs CmdStan (healthy) | gates /51 | h vs `da` | worst model | refined | rc stop |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|
| `da` | shipped defaults (DA 0.8, delta 1) | 1.000 | 1.000 | 0.850 | 42 | 1.00 | 1.000 eight_schools | 0.0023 | 0.029 |
| `da-d2` | DA 0.8, **delta 2** | 1.070 | 1.077 | 0.915 | 42 | 0.98 | 0.679 mcycle_gp | 0.0000 | 0.003 |
| `da06-d2` | DA 0.6, delta 2 | 0.962 | 1.122 | 0.953 | 40 | 1.37 | 0.216 mcycle_gp | 0.0026 | 0.061 |
| `paper08` | Appendix C, Gamma 0.8 | 0.989 | 0.978 | 0.831 | 40 | 1.04 | 0.650 hmm_example | 0.0003 | 0.035 |
| `da06` | DA 0.6 (larger step), delta 1 | 0.834 | 0.899 | 0.764 | 36 | 1.39 | 0.193 mcycle_gp | 0.0217 | 0.254 |
| `stanacc` | Stan `accept_stat__` at 0.8, delta 1 | 0.670 | 0.684 | 0.581 | 38 | 1.03 | 0.343 hmm_example | 0.0043 | 0.125 |
| `paper06` | Appendix C, Gamma 0.6 | 0.604 | 0.689 | 0.585 | 30 | 1.67 | 0.070 mcycle_gp | 0.0664 | 0.402 |
| `da06-d05` | DA 0.6, delta 0.5 | 0.630 | 0.633 | 0.538 | 24 | 1.39 | 0.176 mcycle_gp | 0.1113 | 0.467 |

## Decision

**No arm meets the preregistered rule; the shipped defaults stand.** The rule
required geomean >= 1.15x `da` with no model below 0.85x plus the funnel and
Eight Schools side checks; the side checks did not run (the session hit its
usage limit after the main table completed), and no arm reached 1.15x
regardless.

The informative near-miss is **`delta = 2` at the shipped step** (`da-d2`):
**1.070x** over all 17 models, **1.077x** on the healthy ones, **0.915x**
CmdStan (from 0.850x), the same 42 gates, at an essentially unchanged step
(0.98x) with refinement switched off in practice (0.0% of leaves, 0.3% reverse-
coarser stops). `da06-d2` reaches **1.122x** on the healthy models. Both fail
the no-model-below-0.85x clause on `accel_gp` (0.68x and 0.22x), the model with
the 54% reverse-coarser stop rate - i.e. relaxing `delta` helps everywhere
refinement was only getting in the way, and hurts the one model where it is
doing real work.

## What this means for the project

On posteriors whose stiffness is uniform, WALNUTS reduces to NUTS and the
adaptive machinery is overhead. Its wins are on targets with *localised*
stiffness - Neal's funnel, the T=1000 state-space path - where the fine steps
are spent in a region the global step cannot serve. This is a statement about
the target class, not a defect: it says where to point the sampler and what to
claim for it.

Follow-ups named in the ledger: a preregistered `delta = 2` decision with the
`accel_gp` clause reconsidered (or `delta` adapted per target from the observed
`|dH|` distribution rather than fixed); and a cheaper reverse-coarsening check,
which is what the hard models actually pay for.
