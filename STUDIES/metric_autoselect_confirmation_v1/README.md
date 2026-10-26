# WP85 `metric_autoselect_confirmation_v1`: default-flip confirmation of WP79's auto-selection

**Verdict: the flip DOES NOT QUALIFY. R7 fails, and every other rule holds.**

R7 required the branch choice to be the same across the 6 seeds on at least 20
of 22 models. It held on 19. The three models that switched branch between
seeds are:

| model | dense seeds |
|---|---|
| kidiq | 4/6 |
| garch11 | 2/6 |
| lotka_volterra | 4/6 |

On each of these models both branches passed every gate, and none lost
efficiency. The failure is about the rule's stability across seeds, not about
cost.

## What was run

- **Design:** 22 v7 posteriors x 6 seeds (868501-868506) x {diag, auto} at
  4 x 1,000/1,000.
- **Funnel:** 30 seeds x 4 x 2,000/20,000.
- **Lane:** lane 3, `taskset -c 8-11`, pinned and co-tenanted.
- **Library:** WP79 unchanged, plus the preregistered dimension cap
  (`fc41994a`). Above 256 dimensions the flag gives the plain diagonal run.
  That cap covered radon and grsm_irt.

## Rules

| rule | result | held |
|---|---|---|
| R1 passes | 105 vs 105 (of 132) | yes |
| R2 WP72(c) headline | 2.01 | yes |
| R3 no model < 0.9x | none | yes |
| R4 new divergences | none | yes |
| R5 max \|z\| passing reference | 3.54 | yes |
| R6 bit identity | 122/122 diagonal / diag-cap cells (92 P + 30 F) | yes |
| R7 branch consistency >= 20/22 | **19/22** | **no** |
| R8 funnel P5 (diagonal by construction, 0 dense seeds) | 0.0492 ± 0.0017 | yes |
| R9 lotka_volterra trapped cells | 0 vs 0 | yes |
| D integrity | scoped diff, fingerprints, auto-select tests | yes |

## Reported

- **Wall per gradient, auto/diag:**
  - geomean 1.036;
  - diagonal-branch models 1.026 (the observer's cost);
  - dense-branch models 1.049;
  - funnel 1.048.
- **Dense-branch warmup gradients, auto/diag:** median 0.49 over 40 cells.
  The dense warmup is cheaper, not costlier.
- **Branch matched prediction:** 118/132.
  - kilpisjarvi was predicted dense, but went diag 6/6.
  - kidiq, predicted diag, went dense 4/6. This is unlike WP79's 0/3.

## Reading

The rule is safe: R1, R3, R4, R6 and R9 all hold.

It is still efficient: a 2.0x headline gain.

But three models sit near the linearity bound of 0.5 or the gain threshold of
5. On those models the seed decides the branch.

## Files

- `protocol.json`: the design, including the `proposed_flip` text.
- `PREREGISTRATION.md`: frozen at `d708449b`.
- `run_study.py`, `src/` and `box/`: the harness.
- `artifacts/`: the cells, `summary.json`, `results-table.md`, `box-logs/` and
  the draws manifest.
- `CHECKSUMS.sha256`.
