# nutpie gap decomposition (WP80): preregistration

Frozen before part 1 is computed and before the first telemetry cell. The
machine-readable form is `protocol.json`.

## Question

WP76 put oWALNUTS / nutpie per gradient at 0.699 (statistic (c), fixed 16,
18 Linux seeds), a 1.43x nutpie lead. Where does that lead come from, model
by model and mechanism by mechanism? WP71 (nutpie's metric estimator) and
WP73 (warmup spend) have been ruled out as sufficient explanations. The
output is a ranked list of mechanisms with evidence. There are no candidates
and no flags.

## Part 1: descriptive decomposition (cells on disk, no new run)

For each paired seed, with both cells status ok:

    G = ln(nutpie ESS/grad / oWALNUTS ESS/grad) = A + B + C   (exact)
    A = ln(min bulk ESS, nutpie / oWALNUTS)          ESS per draw (both retain 4 x 1,000)
    B = ln(sampling gradients, oWALNUTS / nutpie)    sampling gradients per retained draw
    C = ln((total/sampling) oWALNUTS / (total/sampling) nutpie)   warmup overhead

- **Inputs.** oWALNUTS cells come from WP64 v7 + ext and WP72; nutpie cells
  from WP76.
- **Per-model values.** Each is a mean over paired ok seeds. A model enters
  with at least 15 of 18 paired seeds.
- **Ranking.** Models are ranked by mean G. Each model's share of the sum of
  G is reported.
- **Also reported.** WP76's per-model (c), and the cell-level approximation
  of refinement spend, ln(gradients_sampling / retained_leaves_built).

**P1.** The three models with the largest G are **sblrc, hmm_drive_0 and
eight_schools_centered**, WP76's three lowest per-model (c) at 0.342, 0.484
and 0.607. accel_gp (0.610) is the nearest rival.

## Part 2: telemetry arm

- **Models.** The three predicted carrying models plus diamonds, where
  oWALNUTS leads (WP76 (c) 1.037).
- **Seeds.** 720701–720703, 4 x 1,000 / 1,000, both samplers, v7 cell code.
- **oWALNUTS diagnostics.** The `telemetry` binary is v7's `main.rs` plus
  per-transition arrays, for retained and warmup transitions: depth, target
  evaluations, leaves attempted and built, refinement attempts, selected
  level, step, maximum energy error, orbit states, reverse-coarser
  rejections, divergence, acceptance and stop. It also writes each chain's
  final mass diagonal and step.
- **nutpie diagnostics.** `store_mass_matrix=True` and
  `store_unconstrained=True`, with every numeric sample stat kept. Both are
  storage flags only.
- **Run.** 24 cells, sequential, one child per cell. Models in the order
  listed, oWALNUTS then nutpie, seeds ascending. No reruns.
- **Bit-identity check.** The seeds are WP72's and WP76's. Each cell is
  checked against the same-seed prior cell: status, gradients, min bulk ESS
  and divergences equal. A mismatch is reported, not repaired.

## Part 3: mechanisms

On the telemetry cells, summing over the 4,000 retained transitions:

    B  = ln(sum oWALNUTS target_evaluations / sum nutpie n_steps) = B4 + B1 + B2   (exact)
    B4 = ln(sum target_evaluations / sum leaves_attempted)      refinement + reverse-check spend
    B1 = ln(e_n / e_o)                                          effective step
    B2 = B - B4 - B1                                            distance per draw (leaves or steps x e)
    ln e = mean over chains of median_i ln(eps * sqrt(Minv_i) / sigma_i)

Definitions:

- **oWALNUTS metric.** Minv_i = 1/M_i, since `mass_diagonal` is M with
  K = 0.5 Σ p²/M_i. eps is the final step.
- **nutpie metric.** Minv is `mass_matrix_inv` and eps is `step_size`, both
  at the last retained draw.
- **sigma_i** is 1.4826 x MAD of the pooled unconstrained retained draws of
  both samplers for that seed.

| | mechanism | diagnostic | criterion (carrying models) |
|---|---|---|---|
| H1 | oWALNUTS adapts a smaller effective step | B1 | >= ln 1.25 on >= 2 of 3 |
| H2 | oWALNUTS travels further per draw (orbit length, depth, unmerged subtrees) | B2, plus depth/n_steps histograms | >= ln 1.25 on >= 2 of 3 |
| H3 | oWALNUTS's diagonal metric matches the posterior scales worse | S_o − S_n, S = SD_i ln(Minv_i/sigma_i²) | >= 0.35 on >= 2 of 3 |
| H4 | refinement and reverse-check spend | B4 | >= ln 1.25 on >= 2 of 3 |
| H5 | lower ESS per draw | A | >= ln 1.25 on >= 2 of 3 |

**Ranking.** The five additive components (A, C, B4, B1, B2) are ranked by
their mean over the three carrying models on the telemetry seeds. H3 is a
cause test for B1 and is reported beside it. Diamonds is reported as the
contrast.

**P2.** B1 ranks first. **P3.** On diamonds, B1 < ln 1.25.

## Platform

AWS c7a.4xlarge, lane 1: `taskset -c 0-3` with `RAYON_NUM_THREADS=4` and
`OMP_NUM_THREADS=1`. Walls are **"pinned, co-tenanted"**. No statistic here
uses a wall. Gradient counts and ESS per gradient are unaffected by
co-tenancy.

## Execution rules and disclosures

- **Freeze.** `PREREGISTRATION.md` and `protocol.json` are committed before
  any cell. The driver refuses cells otherwise.
- **Smoke test (non-evidence seed 11, scratch output, not committed).** One
  sblrc cell per sampler. It exercised both telemetry paths and the part-3
  code. It showed:
  - the mass convention: 1/M tracks the posterior variance; on sblrc's
    betas it is about 11x the variance, against about 1x on sigma;
  - on that one seed, B1 0.36, B2 0.49, B4 0.001 and S_o − S_n 0.68.

  These values were seen before the freeze. P2 was written before the smoke
  test and is left unchanged.
- **Data seen before the freeze.** While designing the study I read one
  WP72 / WP76 sblrc cell at seed 720701 (gradients and steps) and the walls
  of the 24 prior cells. Part 1 has not been computed.
- **Run rules.** Failures are results. There are no reruns and no tuning.
  A driver crash may be relaunched. Raw draws and telemetry are checksummed
  and not committed.
