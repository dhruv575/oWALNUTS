# posteriordb benchmark v7 — preregistration (WP56)

Frozen 2026-10-25 before the first evidence cell, **with one stated exception:
the oWALNUTS commit under test is not fixed yet.** The machine-readable
protocol is `protocol.json`. Seeds 560561–560563 were verified unused by
`git grep -w` over every tracked file at `457119f4` and by `grep -w` over the
sibling worktrees' protocols and preregistrations.

## The open commit, stated plainly

Four sibling confirmation studies are running at the same time as this one:
WP51 (dense-metric defaults), WP52 (`Init::best_of(16)` as the start default),
WP54 (`RejectLeaf` as the default), and WP53 (funnel `delta`). Any of them may
flip a default on `main` in the next ~5 hours. This benchmark is meant to
measure whatever defaults `main` ends up with. So the study runs in two
phases.

- **Phase 1 (now).** Everything except the oWALNUTS commit is frozen in this
  commit: models, seeds, gates, statistics, predictions, decision rule and
  reference-arm versions. Then the CmdStan and nutpie arms run on all 22
  posteriors and 3 seeds. They do not depend on oWALNUTS code.
- **Phase 2.** The commit under test is recorded in a committed
  `AMENDMENT-1.json` **before the first oWALNUTS cell**. It is the hash the
  coordinator sends. If no message has arrived within 1 hour of Phase 1
  finishing, it is `457119f4`, this worktree's base. The worktree's library
  source (`src/`, `integrations/`, `tests/`, `Cargo.toml`) is brought to that
  commit, the harness is rebuilt, and then the oWALNUTS arm runs, followed by
  the funnel row and the descriptive dense arm. `run_posteriordb.py` refuses
  to start an oWALNUTS cell unless the amendment is committed and the
  library source at `HEAD` equals the amended commit.

So the predictions below are made before we know which defaults they will be
tested against. That is deliberate. They are predictions about "main's
defaults after the confirmation wave", whichever way the four studies go. The
harness never names a metric, adaptation, tuning or start rule. It uses
`Sampler::new()` with only the run shape, so a default flip on `main` is what
gets measured. Each cell records the `Debug` form of every default.

## Question

Do the oWALNUTS sampler defaults, as they stand after the WP51–WP54 wave,
stay broad, efficient and reference-consistent on the 17-model house
benchmark? And how do they fare, against CmdStan and nutpie on the same
seeds, on the five posteriors WP46 found hardest (box-constraint corner
traps, a silent funnel, a correlation-1 ridge, and two global-to-local
couplings)?

## Protocol (v6, repeated)

- posteriordb `28f8d3d`. The 17 house posteriors, plus
  `GLMM_Poisson_data-GLMM_Poisson_model`, `seeds_data-seeds_centered_model`,
  `kilpisjarvi_mod-kilpisjarvi`, `science_irt-grsm_latent_reg_irt` and
  `radon_all-radon_hierarchical_intercept_centered`: 22 posteriors.
- Arms: `owalnuts` (decision arm, defaults), CmdStan 2.39.0 (cmdstanpy
  1.3.0, defaults), nutpie 0.16.8 (defaults).
- 4 chains x 1,000 warmup / 1,000 retained. Fresh seeds 560561, 560562 and
  560563, shared by arm. Four threads.
- Gates: rank R-hat <= 1.01, bulk and tail ESS >= 400 on every gate
  parameter, zero retained divergences, finite draws, no sampler error.
  ArviZ 0.23.4.
- Gate parameters. On the 18 reference posteriors (the 17 plus kilpisjarvi)
  they are the reference-draw columns, as in v6. Four of the new five
  (GLMM_Poisson, seeds_centered, grsm, radon) have **no posteriordb reference
  draws**. For those, every constrained parameter-block coordinate is gated,
  as in WP46's gates-only tier, and there is no z statistic.
- Reference-mean z on reference posteriors, with the |z| <= 4 agreement check
  on passing oWALNUTS cells.
- 2,700 s cell timeout. Strictly sequential, one sampling process at a time.
  No reruns.
- Funnel side check: Neal's 10-D funnel at the defaults, given starts
  omega in {-3,-1,1,3}, 4 x 2,000 / 20,000 per seed, MCSE z of P(omega < -5)
  against the exact 0.0478, gate |z| <= 2. The funnel uses its own fresh seeds
  560571–560573; see the pre-freeze deviation below.

Run order. Phase 1 takes models in protocol order, then arms (CmdStan, then
nutpie), then seeds in ascending order. Phase 2 runs the oWALNUTS arm over
models in protocol order, then the funnel seeds, then the dense arm.

**Infrastructure, not evidence.** The BridgeStan libraries are copied from
two sibling builds of the same posteriordb sources: WP48's
`dense_metric_posteriordb_v1/models` for the 17, and WP46's
`posteriordb_breadth_v1/models` for the five. The posteriordb checkout is a
copy of WP46's (commit verified). Three CmdStan executables (diamonds,
gp_pois_regr, accel_gp) are copied from WP48; the other 19 are compiled by
`prepare_competitors.py`. That script also builds the nutpie libraries with
exactly the `bridgestan.compile_model(..., make_args=["STAN_THREADS=true"])`
call that `nutpie.compile_stan_model` makes, into `models/nutpie/`, and the
cell wraps each library in the same `CompiledStanModel` object.
Compilation is excluded from wall, as in v6.

## Statistics

- Pass counts per arm: house /51, new five /15, all /66. The new-five count
  is also reported per model, so it cannot be averaged away.
- Geomean of oWALNUTS / CmdStan min bulk ESS per gradient. This is computed
  over the fixed 16 non-`arma11` models (P3, as in v6), and separately over
  all 22 (reported).
- Geomean of wall per gradient vs CmdStan over the fixed 16 (P4, contended).
- Bulk ESS per second vs nutpie over complete house models (reported, as v6
  P5).

Geomeans use seed-median ratios over models whose three seeds are all
status-ok on both arms. P3 and P4 are unevaluable unless all 16 are complete.

## Predictions (fixed before execution)

| | prediction | reference |
|---|---|---|
| P1 | oWALNUTS passes **>= 42/51** house cells | v6 45/51 (with rescue); CmdStan 34, nutpie 29 |
| P2 | no passing oWALNUTS reference cell has **max \|z\| > 4** | v6 failed at 4.023 |
| P3 | fixed-16 geomean min bulk ESS/gradient vs CmdStan **>= 0.75** | v6 0.848 on 15/16 |
| P4 | fixed-16 geomean wall/gradient vs CmdStan **<= 1.0** | v6 0.825 |
| P5 | oWALNUTS passes **>= 6/15** on the five new posteriors | WP46: 7/15 on these five (0, 0, 2, 2, 3) |
| P6 | oWALNUTS fails `seeds_centered` **0/3 with zero retained divergences** on every cell (the silent funnel) | WP46 0/3, 0 divergences |
| P7 | CmdStan passes **>= 8/15** on the five new posteriors | unmeasured; CmdStan shares the starts and would show divergences on the funnel |
| P8 | funnel tail mass **\|z\| <= 2 on every seed** | v6 -1.04, +0.25, +1.69 |

**Our expectation for P4, stated before running: it fails.** Since WP50, every
native BridgeStan call on Windows is serialised through the owned worker
(`Execution::OwnedSerialised`). WP50C measured that at 3.2x–4.0x wall with
identical draws, and v6 did not have it. P4 is kept because the v6 release
rule contains it.

The dense arm carries no prediction (see below).

## Release rule (as in v6)

**Primary (v6 verbatim).** v7 may replace v5 as the breadth headline for the
commit under test if all three of the following hold:

- all 153 house cells (17 models x 3 arms x 3 seeds) are present;
- P1, P3, P4 and P8 hold;
- every passing oWALNUTS reference cell meets P2.

The five new posteriors are outside the release rule, as in v6, where the
rule covered the 17 only.

**Secondary (labelled, never a substitute).** The same rule without P4,
because P4 measures the Windows owned-worker serialisation rather than the
sampler. The README reports both and leads with the primary.

P5, P6, P7, the all-22 geomean, ESS/s vs nutpie and the dense arm are
reported. They are not release gates. A failed prediction is printed beside
its number. This study changes no default. It measures whatever defaults the
amended commit has.

## Descriptive dense arm (non-decision)

After the main arm and the funnel row, the study runs `Metric::dense()` with
otherwise-default settings, at whatever dense defaults the amended commit
has. It runs on the six correlated-regression posteriors WP48 named
(diamonds, earnings, mesquite, kidiq, nes2000, arK), with the same three
seeds. It is labelled `owalnuts-dense`. It is excluded from every pass count,
geomean, prediction and the release rule. It is reported as gates, ESS per
gradient relative to the defaults arm and to CmdStan, and max |z|, so the
README can show what dense buys.

## Pre-freeze deviation (recorded before the freeze)

While smoke-testing the driver, I used a non-evidence seed (11) and a
scratch output directory. The smoke test of `checks` took its seeds from
`protocol.json`, so it ran the funnel at 560561–560563 on `457119f4` before
this freeze, and I saw the tail-mass z values (+0.06, -0.17 and -0.66). Those
seeds are therefore not fresh for the funnel. The funnel row uses
560571–560573 instead, which were chosen and verified unused (`git grep -w`)
before this freeze. No posteriordb cell at 560561–560563 had been run. The
smoke outputs are not evidence and are not committed.

## Execution rules

All cells are reported. Failures and timeouts are results, and nothing is
tuned after a result is seen. A driver crash may be relaunched. An
interrupted cell without a completed artifact may be rerun from scratch with
the same seed, and the deviation is recorded. Walls are contended (up to
seven agents on 16 hybrid cores), so they are labelled and never used to
interpret sampler behaviour. Raw draws are checksummed and left uncommitted.
Cell metrics, summary, tables, logs and manifests are committed.
