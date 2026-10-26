# WP82: refinement spend on the centred eight schools

**Verdict: no candidate qualifies, and no default changes.**

The telemetry confirms the mechanism:

- The adapted step is set by the bulk. It is 1.18x CmdStan's.
- Refinement concentrates in the funnel neck. 71 % of refined transitions start in the lowest
  log-tau quartile, where a transition costs 184 gradients against CmdStan's 13 leapfrogs.
- Refined transitions take 72 % of sampling gradients.

All three levers move the centred model a long way (1.6–2.5x the default), but each fails
elsewhere:

- **`costda`:** misses K1 (0.577) and fails K4 (gp_pois_regr 0.75).
- **`stanacc`:** fails the funnel (P5 +1.18 s.e.) and K4 (hmm_example 0.16).
- **`levels2`:** truncates the neck. Funnel P5 is 0.0075, and it has 256 centred divergences.

K5 also failed for every candidate, because the directional `cost_weighted_acceptance` test failed
on Linux (see Deviations).

Design and rule: `PREREGISTRATION.md`, `protocol.json` (committed `7966207f`, Amendment 1
`62a0caad`). Tables: `artifacts/results-table.md`; data: `artifacts/summary.json`.

## Telemetry (6 seeds 821821–821826, 4 x 1,000/1,000)

| | oWALNUTS | CmdStan |
|---|---:|---:|
| adapted step, centred (median) | 0.157 | 0.149 |
| sampling gradients per transition, centred | 64.7 | 21.1 |
| refined fraction / refined gradient share | 0.253 / 0.719 | — |
| gradients per transition, log-tau Q1 → Q4 | 184 / 17 / 24 / 33 | 13 / 20 / 28 / 37 (leapfrog) |
| refined fraction, Q1 → Q4 | 0.72 / 0.18 / 0.07 / 0.04 | — |
| terminal-window acceptance | 0.797 | 0.773 (retained 0.833; Q1 0.475) |
| retained divergences, 6 cells | 12 | 692 |

- **Refinement depth (transitions by level):** 2,972 at level 1, 1,231 at level 2, and 1,867 at
  levels 3–7.
- **CmdStan in the neck:** CmdStan makes its trajectories *shorter* there (Q1/Q4 = 0.35), at
  acceptance 0.48, and diverges on 11 % of its neck draws. oWALNUTS keeps the step and refines
  (Q1/Q4 = 5.6).
- **WP72 ratio on these seeds:** the default is at 0.269x CmdStan per total gradient (interval
  0.13–1.62) and 0.187x per sampling gradient.
- **Non-centred twin:** 0.867x. Its refined fraction is 0.054, so P4 (< 0.05) narrowly failed.
- **Predictions:** P1, P2 and P3 held; P4 failed.

## Rule

| candidate | K1 centred vs CmdStan >= 0.60 | K2 gates / divergences | K3 funnel P5 ± s.e. | K4 regression (passes, geomean >= 0.95) | K5 | qualifies |
|---|---|---|---|---|---|---|
| `costda` | **0.577** | 0 vs 0, 0 vs 12, holds | 0.0466 ± 0.0033, holds | 15 vs 15, **0.909** | **fails** | no |
| `stanacc` | 0.929, holds | 0 vs 0, 3 vs 12, holds | **0.0524 ± 0.0039** | **14 vs 15, 0.618** | **fails** | no |
| `levels2` | 0.799, holds | **256 vs 12 divergences** | **0.0075 ± 0.0025** | 15 vs 15, 1.034, holds | **fails** | no |

The default's funnel P5 is 0.0466 ± 0.0022.

**On the centred model vs the default** (per total gradient):

| candidate | ratio | adapted step | refined fraction | sampling gradients per transition |
|---|---:|---:|---:|---:|
| `costda` | 1.64 | 0.136 | 0.216 | 47.6 |
| `stanacc` | 2.03 | 0.183 | — | 38.0 |
| `levels2` | 2.46 | — | — | 20.3 |

The `levels2` gain is bought by ending neck orbits early. That truncation is what biases the funnel
tail.

**Per-model K4 ratios:**
- `costda`: noncentred 0.87, sblrc 1.02, arK 0.96, gp_pois 0.75, hmm_example 0.97.
- `stanacc`: hmm_example 0.16, sblrc 0.74, arK 0.77.

## Predictions vs outcome

- **`costda`:** I predicted K1 of about 0.45, a fail. The outcome was 0.577, still a fail.
- **`stanacc`:** I predicted a K1 fail (0.45–0.55). It passed K1 at 0.93, but failed K3 and K4.
- **`levels2`:** I predicted a K1 fail (about 0.45) and a K3 fail. It passed K1 (0.80) and failed
  K3, as predicted.

## Deviations

- **Amendment 1 (`AMENDMENTS.md`).** The first launch ran no cell, because the protocol's source
  revision was prose.
- **Second launch.** It also ran no cell: the launch script deleted the study directory, and a
  checkout without `--hard` did not restore unchanged files. The script was fixed, with no
  protocol change, and the third launch ran every phase.
- **K5 failure.** The test `refined_leaves_shrink_the_adapted_step` asserts that at least 3 of 4
  chains get a smaller step. That held on Windows but failed on Linux, at 2 of 4, because Linux
  libm gives different draws. It is a directional property claim and was too strong. The integrity
  tests passed on Linux:
  - `kernel_fingerprint` with flags off;
  - bit-identity at one level;
  - off by default.

  Under the frozen rule, K5 still fails. The verdict does not depend on it: every candidate also
  fails another clause.

## Run record

- **Where and when:** lane 2 (cores 4-7), co-tenanted, on 2026-10-26.
- **Cells:** 24 E + 18 C + 57 R (3 reused from E) + 40 funnel. All were ok, with no reruns.
- **Checksums:** `CHECKSUMS.sha256` covers 258 files. The `.npz` draws are hashed and kept on the
  lane.
