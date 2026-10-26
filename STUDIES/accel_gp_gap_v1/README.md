# WP70: the accel_gp ESS-per-gradient gap

## Verdict

**No candidate qualifies, and none of the three preregistered hypotheses met its frozen
criterion. Post hoc, one mechanism stands out: on accel_gp the adapted step decides the
share of orbits cut short by a failed reverse check, and that share decides mixing. A smaller
step fixes mixing but costs gradients in proportion, so the per-gradient gap stays.**

The run used three fresh seeds (700711–700713), 4 x 1,000/1,000, and v7 gates and metrics.
oWALNUTS ran through BridgeStan 2.9.0 on the replicated dispatch WP65 qualified, against
CmdStan 2.39.0 at defaults. Every process was pinned to lane 2 (cores 4-7) of the shared box,
with three other lanes active. Walls are not used. This is diagnostic and research-flag
evidence only; no default and no library code changed.

| | oWALNUTS / CmdStan, accel_gp min bulk ESS per gradient | accel_gp gates | control passes /15 | control geomean vs default | rule |
|---|---:|---:|---:|---:|---|
| default (baseline) | **0.567** | 0/3 (CmdStan 0/3, 37–174 divergences) | 15 | 1 | — |
| `cand-target095` (target_accept 0.95) | 0.616 (R1 fails) | **3/3** | 15 | 0.804 (R3b fails) | **not qualified** |
| `cand-depth12` (max_depth 12) | 0.084 (R1 fails) | 0/3 | 14 (R3a fails) | 0.981 | **not qualified** |
| `cand-warmup2000` (2,000 warmup) | 0.192 (R1 fails) | 0/3 | 15 | 0.740 (R3b fails) | **not qualified** |

## Hypotheses and diagnostics (phase 1, `artifacts/diagnosis.md`)

| | hypothesis | diagnostic | value | criterion | outcome | prediction |
|---|---|---|---|---|---|---|
| H1 | orbit truncation by failed reverse checks | `reverse_coarser_accepted` share of retained transitions; median integration time vs CmdStan | **0.55** (0.51–0.63); **0.87** (0.40, 0.87, 0.90) | >= 0.40 and <= 0.60 | **not supported** (the time clause fails) | supported: wrong |
| H2 | depth cap | `maximum_depth` stop share | 0.0001 | >= 0.05 | not supported | not supported: right |
| H3 | adaptation further from posterior scales than CmdStan's | q90 \|ln(adapted / reference variance)\|, oWALNUTS / CmdStan | 1.43 (0.24–0.25 vs 0.17–0.19) | >= 1.5 | not supported, narrowly | not supported (point 1.1): right |

The baseline prediction P0 (ratio in [0.25, 0.55]) **failed narrowly at 0.567**. CmdStan's
median seed was weak (min bulk ESS 574, 174 divergences), and the v7 figure on Windows seeds
was 0.35.

Reported diagnostics (not gated):

- **Reverse-coarser stops.** More than half of oWALNUTS's retained orbits end on one. Those
  orbits integrate a median of 0.8–1.2 time units, against 3.8–4.0 for orbits that end at a
  U-turn; 30–39 % of selected leaves are refined. The median over all transitions is still
  0.87x CmdStan's, so the frozen H1 statistic, a median, does not see the short half.
- **Work per transition.** Gradients per retained transition are 0.60x CmdStan's (305–468 vs
  604–850). CmdStan reaches depth 10 on 18–53 % of its transitions; oWALNUTS stops at its depth
  cap on almost none.
- **Step and warmup.** The adapted step is 1.06x CmdStan's (0.0073–0.0079 vs 0.0065–0.0079).
  The warmup gradient share is 0.41–0.53 vs 0.42–0.51.
- **Slowest parameter.** The min-ESS parameter is a GP coefficient or `sdgp_1` for oWALNUTS,
  and `lscale_1` for CmdStan.

## What the candidates show (post hoc, descriptive)

The four oWALNUTS arms on accel_gp form a dose-response in the adapted step:

| arm | median step | reverse-coarser stop share | median integration time | min bulk ESS (3 seeds) | gradients |
|---|---:|---:|---:|---|---:|
| `cand-target095` | 0.0050–0.0052 | 0.11–0.15 | 4.8–5.2 | 1,023–1,579 | 7.3–7.4 M |
| default | 0.0073–0.0079 | 0.51–0.63 | 2.5–3.6 | 294–611 | 2.6–3.2 M |
| `cand-warmup2000` | 0.0087–0.0095 | 0.72–0.80 | 1.2–1.7 | 11–356 | 3.4 M |
| `cand-depth12` | 0.0093–0.0099 | 0.76–0.80 | 1.0–1.6 | 49–136 | 2.4 M |

- **Smaller step.** At a step 0.68x the default's, reverse-coarser stops fall from 55 % to 14 %
  and the median integration time rises to about 1.2x CmdStan's. The ESS rises 2.7x, and accel_gp
  passes its gates on 3/3 seeds. No oWALNUTS or CmdStan accel_gp cell passed in WP56, WP62 or this study's other arms.
  The price is 2.5x the gradients, so per gradient the gain is only 1.09x the default (0.62x
  CmdStan). The controls pay 15–30 % (geomean 0.80), all except gp_pois_regr (1.01).
- **Longer warmup or deeper cap.** Both make dual averaging settle at a larger step (+20–30 %),
  probably because they dilute or avoid the early crash-driven step cuts WP40 described. The
  reverse-coarser share then rises to about 0.75, orbits shorten, and ESS collapses.
  `cand-depth12` is bit-identical to the default on eight schools, arK and garch, where the cap
  never binds, and loses a gp_pois_regr gate.

So the reading of WP40 and open question 1 holds on Linux with fresh seeds. On accel_gp the
acceptance-0.8 fixed point sits at a step where most orbits are cut by a failed reverse check.
A smaller step removes the truncation but buys mixing at roughly its gradient cost. The gap to
CmdStan per gradient therefore stays at about 0.6x under every setting tested.

Two caveats:

- H1's frozen statistic was a median, and it missed a bimodal effect. This study only records
  that miss; it does not re-decide H1.
- The dose-response is four arms x three seeds, post hoc.

## Recommendations

- **No default change and no research flag.** `target_accept = 0.95` is the setting to document
  for users who need accel_gp-type GP posteriors to pass the gates. It passed 3/3 here at 2.5x
  the gradients; CmdStan fails 0/3 at defaults. It is not a per-gradient improvement.
- **The open kernel question is unchanged:** a reverse check or step statistic that does not
  cut half the orbits at the 0.8 fixed point. A follow-up should preregister the reverse-coarser
  stop share itself as the statistic, and the step-dose design, before any new candidate.

## Reproduce

On the box, in `~/lanes/accel_gp_gap_v1/` with `env.sh` sourced and every command prefixed with
`taskset -c 4-7`:

```
python build_models.py 3 && cargo build --release -j4 --locked
python run_gap.py run --phase=1 && python run_gap.py diagnose
python run_gap.py run --phase=2 && python run_gap.py analyze && python checksums.py
```

The single run happened 2026-10-26 02:05–02:12 UTC at study commit `9d8a015d` (library
`d39efaad`). All 75 cells were recorded, with no error, timeout or rerun.

- Results: `artifacts/results-table.md`, `artifacts/summary.json`, `artifacts/diagnosis.{md,json}`.
- Changes to the copied v7 and WP65 code: `PREREGISTRATION.md`.
- Raw draws, per-transition arrays and CmdStan CSVs stay on the box; the draws and arrays are
  hashed in `CHECKSUMS.sha256`.
