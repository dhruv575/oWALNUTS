# WP63 delta2_default_confirmation_v1: preregistration

Frozen 2026-10-25, before the first evidence cell. `protocol.json` is the
machine-readable copy and wins on any discrepancy. Amendments may cover only
cells that have not yet run.

## Question

Should `delta = 2` (`Tuning::max_error`, the per-leaf Hamiltonian-error
tolerance, currently 1) become the sampler default?

This is a default-flip confirmation. The flip is implemented in this worktree
only if the frozen rule below passes.

## Commit under test

Main `33a8e39d`. The worktree was fast-forwarded to it. Its sampler, kernel
and defaults are those of `f097391c`, the posteriordb v7 commit:

- `best_of(16)` starts (WP52);
- `RejectLeaf` (WP54);
- no chain rescue (WP36).

The driver refuses to run evidence cells if `src/`, `integrations/`, `tests/`
or `Cargo.toml` differ from `33a8e39d`. It also refuses if the preregistration,
protocol, driver or harness are uncommitted.

## Arms (oWALNUTS only)

- `default`: `Sampler::new()`, which sets only the run shape, four chains,
  four threads, the seed and `admit_worst_case`. `Tuning::default()` has
  delta 1.
- `delta2`: the same, plus `.tuning(Tuning::default().max_error(2.0))`.

## Blocks (strictly sequential, in this order; one sampling process at a time)

- **A.** The 17 house models of WP34/WP49 × 2 arms × seeds 630601–630604.
  - Settings: 4 × 1,000/1,000, paired by seed.
  - Order: models as listed in the protocol, then seeds ascending, then arm
    (`default` before `delta2`).
- **B.** `mcycle_gp-accel_gp` and `bball_drive_event_0-hmm_drive_0` × 2 arms ×
  seeds 630611–630614.
  - Same settings as A.
- **C.** Neal's 10-D funnel × 2 arms × seeds 630621–630632.
  - The same 12 seeds are used for both arms.
  - Settings: 4 × 2,000/20,000, starts ω ∈ {−3, −1, 1, 3}.
  - The binary is the WP53 one.

All 20 seeds were verified unused with `git grep -w`. Smoke tests used seeds
630691–630693 in a scratch directory, and they are not evidence. A failed or
errored cell is a result. No cell is rerun and nothing is tuned after results.

## Statistics

- **Cell gates:**
  - rank R-hat ≤ 1.01;
  - bulk ESS ≥ 400 and tail ESS ≥ 400;
  - zero retained divergences;
  - finite draws;
  - no sampler error.

  All are computed with ArviZ 0.23.4 over the posteriordb reference
  parameters. The reference z is reported, and max |z| is taken per cell.
- **Cell efficiency:** min bulk ESS divided by `gradients_total`, which
  includes start search, warmup and sampling.
- **Paired geomean over A:** for each model, the geomean over its paired
  seeds of delta2 / default. A pair counts if both cells finished, whether or
  not they passed the gates. The primary statistic is the geomean of the 17
  model ratios.
- **Leave-one-seed-out (LOSO):** the primary recomputed with each A seed left
  out. LOSO min is the minimum of the four values.
- **Gates:** passing cells per arm over A+B, which is 76 cells per arm.
- **Funnel tail:** per arm, the mean of the 12 per-seed P(ω < −5) estimates.
  - Between-seed SE = sd / √12.
  - The "1 SE" in R5 and P4 is the SE of the difference,
    √(SE_default² + SE_delta2²).
- **Funnel divergences:** retained divergences per arm, summed over the 12
  seeds and 4 chains.

## Predictions (frozen)

| id | prediction |
|---|---|
| P1 | paired geomean over A in [1.05, 1.15] |
| P2 | LOSO minimum ≥ 1.0 |
| P3 | delta2 gate passes (A+B) within 1 of the default's |
| P4 | pooled funnel tail mass of delta2 within 1 SE of the default's |
| P5 | funnel divergences of delta2 within 1.5× of the default's (ratio in [1/1.5, 1.5]) |

## Decision rule (frozen)

Flip if and only if ALL of the following hold, and every cell of A, B and C is
present:

| id | condition |
|---|---|
| R1 | paired geomean over A ≥ 1.08 |
| R2 | LOSO minimum ≥ 1.00 |
| R3 | delta2 gate passes (A+B) ≥ the default's − 1 |
| R4 | no passing delta2 cell (A+B) has max \|z\| > 4 |
| R5 | delta2 pooled funnel tail mass ≥ the default's − 1 SE (of the difference), with all 12 delta2 funnel cells completed |
| R6 | delta2 funnel divergences ≤ 1.5 × the default's (0 if the default has 0), with all 12 delta2 funnel cells completed |

**If the rule passes:**

1. Set the `Tuning::default()` max_error to 2.0 in `src/sampler.rs`.
2. Pin the new default in `tests/kernel_fingerprint.rs`.
3. Bump `ALGORITHM_REVISION` per the walnutpie docs if retained draws under
   the defaults change.
4. Add a CHANGELOG entry that names WP63 and states that posteriordb v7 was
   measured at delta = 1, so a v8 is required.
5. Run `cargo test` (GNU toolchain).
6. Commit on `wt/posteriordb-v7`, with no merge, push or tag.

**If it fails:** document the result and change nothing in the library.

## Prior evidence

- WP34: delta2 / default = 1.070×.
- WP49: d2 / da = 1.141× on these 17 models over 3 seeds (d2 had 43 gate
  passes).
- WP53, 30 funnel seeds:

  | arm | pooled P(ω < −5) | divergences |
  |---|---|---|
  | delta2 | 0.0455 ± 0.0010 | 37 |
  | default | 0.0458 ± 0.0014 | 43 |

  Both arms are about 4–5 % below the exact 0.0478.
