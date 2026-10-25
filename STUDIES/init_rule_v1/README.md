# init_rule_v1 (WP43): candidate-pool start rules

**Verdict: supported, with a narrow margin.** `Init::best_of(16)` meets every
clause of the frozen decision rule. It removed both start-lottery failures
on these seeds (`hmm_drive_0` second mode, `lotka_volterra` frozen chain) and
has zero hidden-mode cells. Its geomean min-bulk-ESS per gradient is 1.258x
the default (init counted), and the funnel stays within |z| <= 1.39. The
mechanical recommendation is `best16`. The gate margin is only +1 (72 vs 71
credited passes of 85): best16 gained the two lottery cells and lost one
`gp_pois_regr` cell. The whole efficiency gain comes from the three
start-sensitive models. On the other 14 models best16 is 0.967x, within seed
noise (z -0.73) but not a gain. `Init::median_of(16)` had the most credited
passes (73) and failed D4: funnel z -3.19 on seed 943105.

No default was changed. The study ships the opt-in variant only:
`Init::Candidates`, `Init::best_of`, `Init::median_of`, `StartSelection`,
`candidate_starts`, `CandidateStarts`. `Init::uniform()` and `Init::Given`
are unchanged, `candidate_starts(.., k = 1, ..)` equals `uniform_starts`
bit for bit (tested), and `cargo test` is green.

## Evidence

All 255 posteriordb cells (17 models x 5 seeds x 3 arms) and 15 funnel cells
ran exactly once, in protocol order, on 2026-10-24 between 17:43 and 22:58
local time. There were no process errors or reruns. Preregistration and
harness are frozen at `ac4b873d`, which precedes the first cell.

| arm | credited passes /85 | hidden-mode | R-hat failures | init evals (total) | geomean ESS/grad vs default | funnel max abs z | decision |
|---|---|---|---|---|---|---|---|
| default `Init::uniform()` | 71 | 0 | 12 | 345 | 1 | 0.56 | reference |
| best16 `Init::best_of(16)` | 72 | 0 | 11 | 5,503 | **1.258** | 1.39 | **qualifies** |
| median16 `Init::median_of(16)` | 73 | 0 | 10 | 5,503 | 1.112 | **3.19** | fails D4 |

Init cost: best16 and median16 spend about 64 evaluations per cell (73-78 on
`lotka_volterra`, where `rk45` rejects some draws). The median is 0.024 % of
the gradients.

**The lottery models** (per-model ESS/gradient ratio vs default, paired
seeds):

- `hmm_drive_0`: on default seed 943101, chain 3 ended 71.8 reference SD
  from the reference (R-hat 1.09, a visible failure that `ChainDisagreement`
  names). best16 and median16 passed 5/5 with no chain off the reference.
  Ratio 3.09x for best16, 2.13x for median16. The second-mode chain's start
  log density was -8,500. That was not the worst start: chain 1 started at
  -32,564 and found the main mode. Start density is not a mode oracle. Still,
  best16's median start density is -3,269, against -31,870 for default.
- `lotka_volterra`: on default seed 943105, chains 0 and 2 started at -51,643
  and -18,458, ended 611 and 1,165 reference SD away, and one froze
  (11.5 M gradients). `ChainDisagreement` named nobody, because two chains
  disagree. median16 failed on the same seed: chain 3, the lowest-density
  start of its four (-4,047), went 595 SD away and froze. best16 passed 5/5.
  Ratio 7.12x for best16, 2.31x for median16.
- `arma11`: every arm passed 5/5. The default starts at log density down to
  -2.8e56 cost warmup crawl, and best16 is 3.61x (median16 1.53x).

**Cost on the other 14 models.** best16 per-model ratios: `one_comp` 0.69,
`gp_pois_regr` 0.80, `kidiq` 0.88, `nes` 0.89, `earnings` 0.91, `mesquite`
0.92, `arK` 0.97, `hmm_example` 1.03, `eight_schools_centered` 1.05, `sblrc`
1.06, `eight_schools_noncentered` 1.08, `diamonds` 1.08, `garch` 1.09,
`accel_gp` 1.21. Geomean 0.967. median16 is 0.985 on the same set. Under
the null, the seed-to-seed spread of the default arm gives a two-SD band of
0.91 to 1.10 for this 14-model geomean, so neither figure is distinguishable
from zero effect. A real cost of a few percent on healthy models is not
excluded by five seeds. best16's one lost cell is `gp_pois_regr` 943102:
R-hat 1.011, tail ESS 105, chain 3 named by `ChainDisagreement`, no chain off
the reference. It looks like slow mixing rather than a mode.

**Hidden modes.** None in any arm. Every `hmm_drive_0` cell that passed
R-hat has max |mean - ref| <= 0.06 reference SD.

**Funnel** (P(omega < -5), MCSE z per seed 943101-943105):

| arm | z by seed | mean of the five estimates |
|---|---|---|
| default (house starts) | +0.38, +0.02, -0.41, +0.56, -0.04 | 0.0488 |
| best16 (uniform(-3,3) pool, max density) | -0.63, +1.39, +1.14, +1.09, -1.32 | 0.0522 |
| median16 (uniform(-3,3) pool, median density) | +0.77, +0.20, -0.19, -1.35, **-3.19** | 0.0433 |

The exact value is 0.0478. best16 places every start at omega in [-0.5, 1.5],
the funnel's mouth, and the tail is unbiased. median16's failing seed has no
collapsed chain: all four chains are low (0.015-0.040), with omega R-hat
1.011. Fifteen funnel cells at this z resolution cannot separate a
start-rule effect from a 1-in-50 draw. Under the frozen rule it is a
failure.

## Predictions

| | prediction | observed | held |
|---|---|---|---|
| P1 | default 70-74 credited; centered eight schools 5/5 fail; `accel_gp` 2-3 fail | 71; 5/5; `accel_gp` **5/5** fail | no (`accel_gp` clause) |
| P2 | default 1-2 off-reference HMM seeds; best16 0; best16 LV 5/5 | 1; 0; 5/5 | yes |
| P3 | best16 credited exceeds default by 1-3 | +1 | yes |
| P4 | best16 zero hidden-mode | 0 | yes |
| P5 | best16 geomean in [1.00, 1.15] | 1.258 | no (above; lottery cells weigh more than predicted) |
| P6 | median16 indistinguishable from default | +2 credited, 1.112, no HMM seed off | no |
| P7 | funnel abs z <= 2 every seed, all arms | median16 -3.19 | no |
| P8 | best16 median start density above default on all 17 | 17/17 | yes |
| P9 | best16 qualifies, median16 does not | yes | yes |

## Reading

Ranking candidates by density does what the open question asked on these
seeds. It took the two lottery cells out, and nothing hid a mode. The
mechanism is coarse. Low-density starts are the ones that freeze on
`lotka_volterra` and crawl on `arma11`, and picking the best of 16 removes
the far tail of start densities. It does not identify basins: the
`hmm_drive_0` second-mode chain was not the lowest-density start. The rule
puts every start in a much smaller, higher-density region. On a target with
two comparably weighted modes this could make R-hat less able to see the
second mode. These 17 models have no such target, so the zero-hidden-mode
result does not prove that risk away. That is the remaining argument against
making it the default without a dedicated multimodal check.

The +1 gate margin rests on two lottery cells against one ordinary failure.
A different five seeds could easily give a tie or a loss. The robust findings
are the lottery removal (2/2 lottery cells fixed, 0 created on those models)
and the absence of hidden modes. The 1.258x headline is real but comes from
three models.

## Recommendation

1. Keep `Init::best_of(16)` as a documented opt-in now (shipped here).
2. Before flipping the default, run a dedicated preregistered confirmation.
   Use fresh seeds and weight it toward the lottery models (`hmm_drive_0`,
   `lotka_volterra`, `arma11`). Add a multimodal safety target with two
   known, comparably weighted modes, so the hidden-mode risk is measured where
   it can occur, and enough healthy-model seeds to bound the 0.967x
   non-lottery figure. The frozen rule of this study says recommend; this
   study cannot also rule out that risk.
3. Do not pursue `median_of`. It does not reliably remove the lottery (it
   failed the same `lotka_volterra` seed) and it failed the funnel gate.

## Files

- `PREREGISTRATION.md`, `protocol.json`: frozen at `ac4b873d`.
- `src/main.rs` (cell harness), `src/bin/funnel.rs`, `run_init.py` (driver
  and analysis; posteriordb_bench_v6 metrics reused), `checksums.py`,
  `CHECKSUMS.sha256`.
- `artifacts/cells/*.json` (255 cells), `artifacts/funnel/*.json` (15),
  `artifacts/summary.json`, `artifacts/results-table.md` (every cell, start
  log densities, per-model ratios, funnel, predictions),
  `artifacts/run-log.txt`, `artifacts/analyze-log.txt`,
  `artifacts/measured_on.json`. Raw draws (`artifacts/draws/`, 169 MB) are
  ignored.
- Environment: study-local `.venv` (Python 3.11.16, ArviZ 0.23.4, BridgeStan
  2.9.0, posteriordb 0.2.0), posteriordb checkout `28f8d3d`, and models
  compiled locally with BridgeStan 2.9.0 (no `STAN_THREADS`). All are
  ignored. The posteriordb_bench_v6 assets named in older studies no longer
  exist on disk.
- Contention: nine sibling agents were running. Diamonds cells took about
  16 minutes each, against 90 s in v6. Walls are not evidence and are not
  reported.
