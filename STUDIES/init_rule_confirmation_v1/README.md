# init_rule_confirmation_v1 (WP52): best-of-16 starts as the default

**Verdict: supported under the frozen rule, with a cost the rule did not
price.** `Init::best_of(16)` met all four clauses of the preregistered
default-flip rule:

- **F1:** geomean min-bulk-ESS per gradient 1.254x `Init::uniform()`;
- **F2:** 42 vs 42 credited gate passes of 51;
- **F3:** funnel |z| <= 1.11 on every seed;
- **F4:** no hide event on the two-mode target. R-hat saw both modes on all
  three seeds in both arms.

The default is flipped on this branch: `Init::default()` and
`Sampler::run_from_random_starts` now use `Init::best_of(16)`.

The gain sits on two start-lottery cells, `arma11` and `lotka_volterra` seed
952203, which uniform lost. The other 14 models are 0.862x, against WP43's
0.967x. best_of_16 also lost two cells that uniform passed:

- `earnings` 952201: warmup step collapse on one chain.
- `hmm_drive_0` 952202: one chain spent its first 46 retained draws in a second
  mode. Rank R-hat was 1.0087, so the cell is **hidden-mode** under the WP43
  definition. `Summary::chain_warnings` named that chain.

WP43's rule had a zero-hidden-mode clause (D2) and would have failed on this
cell. The WP52 rule has none: it counts a hidden-mode cell only as a lost gate.
The merge decision should weigh this; see *Reading*.

## Evidence

All cells ran exactly once, in protocol order, on 2026-10-25 between 02:38 and
04:17 local time, with no process errors and no reruns. The preregistration
and harness were frozen at `f8f1b0b4`, before the first cell. The cells were:

- 6 two-mode cells and a 2 x 1,000-seed start-only tally;
- 6 funnel cells;
- 102 posteriordb cells (17 models x 3 seeds x 2 arms).

### Decision clauses

| clause | threshold | observed | holds |
|---|---|---|---|
| F1 geomean ESS/gradient ratio | >= 1.10 | **1.254** (lottery 3: 7.20; other 14: 0.862) | yes |
| F2 credited passes | >= uniform - 1 | 42 vs 42 | yes |
| F3 funnel best_of_16 |z| | <= 2 every seed | max 1.11 | yes |
| F4 two-mode hide events | none | none | yes |

### Two-mode target

The target is `0.7 N(+4 e1, I) + 0.3 N(-4 e1, I)` with d = 10, its two means
symmetric about the start box. In the mode strings, A = major and i = minor.
A chain's start mode is the side of `x1 = -0.106` its start falls on, and its
end mode is where the majority of its retained draws lie.

| seed | arm | start | end | retained fraction major per chain | max split R-hat | chain_warnings | pooled major (exact 0.700) |
|---|---|---|---|---|---|---|---|
| 952201 | uniform | iAii | AAAi | 0.91, 1.00, 1.00, 0.48 | 1.270 | none | 0.848 |
| 952201 | best_of_16 | iAAA | iAAA | 0.00, 1.00, 1.00, 1.00 | 1.528 | RHat chain 0 | 0.750 |
| 952202 | uniform | AAiA | AAAi | 1.00, 1.00, 0.78, 0.00 | 1.453 | none | 0.694 |
| 952202 | best_of_16 | iiiA | AiiA | 1.00, 0.00, 0.00, 0.98 | 1.713 | none | 0.496 |
| 952203 | uniform | AAiA | AAiA | 1.00, 0.64, 0.00, 1.00 | 1.526 | none | 0.660 |
| 952203 | best_of_16 | iAAA | iiAA | 0.00, 0.33, 1.00, 1.00 | 1.559 | none | 0.583 |

Every cell has at least one minor-mode chain and R-hat above 1.27. Uniform
detected the second mode on 3/3 seeds and so did best_of_16, so there is no
hide event.

Chains are not locked to their start basin. Warmup moved chains across the
8-SD gap, in both directions, in 4 of the 6 cells (e.g. uniform 952201 went
iAii to AAAi). Seven chains crossed once more during retained sampling. So
the start mode alone overstates the hiding risk.

**Start-only tally** (1,000 seeds per arm, start rule only, no sampling):

| | uniform | best_of_16 |
|---|---|---|
| chains starting in the minor basin | 47.5 % | 32.6 % |
| histogram of minor starts per 4-chain seed (0..4) | 67, 300, 359, 213, 61 | 213, 395, 280, 98, 14 |
| seeds with every chain in the major basin | 6.7 % | 21.3 % |
| seeds with every chain in one basin | 12.8 % | 22.7 % |

This matches the pre-run design calculation (major-start probability 0.527 and
0.672). Best-of-16 does bias starts toward the dominant mode: single-basin
four-chain starts rise 1.8x. On three sampled seeds that bias did not hide the
mode.

### The 17 house models

The per-model ratio is best_of_16 over uniform, a paired-seed geomean of min
bulk ESS per gradient, with init counted:

| model | ratio | credited uniform | credited best_of_16 |
|---|---|---|---|
| eight_schools_noncentered | 1.085 | 3 | 3 |
| eight_schools_centered | 0.524 | 0 | 0 |
| diamonds | 0.963 | 3 | 3 |
| earnings | **0.208** | 3 | **2** |
| mesquite | 0.863 | 3 | 3 |
| kidiq | 0.835 | 3 | 3 |
| sblrc | 0.878 | 3 | 3 |
| nes | 0.986 | 3 | 3 |
| arK | 0.983 | 3 | 3 |
| arma11 | **59.78** | **2** | 3 |
| garch | 1.162 | 3 | 3 |
| gp_pois_regr | 1.044 | 3 | 3 |
| hmm_example | 1.194 | 3 | 3 |
| hmm_drive_0 | **0.365** | 3 | **2** |
| one_comp | 1.070 | 2 | 2 |
| lotka_volterra | **17.08** | **2** | 3 |
| accel_gp | 1.164 | 0 | 0 |

The cells that decide the comparison:

- **uniform `arma11` 952203** (lost by uniform). Chain 3 started at
  log density -2.4e115 and froze: step 7e-21, 1,000 divergences, 66.7
  reference SD off, R-hat 1.53. `chain_warnings` flagged chain 3 (step and
  density) and `ChainDisagreement` named it. best_of_16's starts on all three
  seeds were between -431 and -168, and it passed 3/3. On the two seeds both
  arms passed, best_of_16 was still about 3.7x per gradient: the warmup crawl
  from huge-negative starts, which WP43 also reported.
- **uniform `lotka_volterra` 952203** (lost by uniform). Chain 3 started at
  -31,307, collapsed to step 2.5e-4 and ended 1,290 SD off, with R-hat 1.60.
  `chain_warnings` flagged it. best_of_16 passed 3/3, with starts between
  -1,031 and -287.
- **best_of_16 `earnings` 952201** (lost by best_of_16). Chain 1 started at
  -151,327, the lowest best-of-16 start on that seed, collapsed in warmup to
  step 5.9e-4 (median 0.016), and gave bulk ESS 9 and R-hat 1.38.
  `chain_warnings` flagged it (step, warmup density, R-hat) and
  `ChainDisagreement` named it. The chain was 2.2 SD off, not in a different
  mode. On `earnings`, best-of-16 does not reach a well-scaled region: its
  starts are still -2e4 to -2e5.
- **best_of_16 `hmm_drive_0` 952202** (lost by best_of_16, hidden-mode). Chain
  3 started at -3,631, a typical best-of-16 start; uniform's starts on the same
  seed went down to -82,092. It ended warmup in the second HMM mode, with
  `lambda[2]` near 3 against the reference 0.076, and returned to the main mode
  after 46 retained draws. Results:
  - The cell mean of `lambda[2]` was 3.14 reference SD off, and chain 3's own
    mean was 12.6 SD off.
  - Rank R-hat was 1.0087: 46 of 4,000 draws barely move rank-normalised
    R-hat. `ChainDisagreement` did not fire.
  - `WarmupLogDensity` warnings named chains 1 and 3 (median log density -1,963
    vs -1,931).

  This is the failure WP43 described: start density is not a mode oracle. Here
  it hit the best-of-16 arm, whereas in WP43 (seed 943101) it hit uniform.

Other observations:

- Hidden-mode cells: uniform 0, best_of_16 1.
- `chain_warnings` fired on 2 uniform cells and 4 best_of_16 cells. It covered
  every lost lottery cell in both arms, plus `hmm_drive_0` 952203 and
  `accel_gp` 952202 under best_of_16, which both passed R-hat.
- Init cost: 64 evaluations per cell (71-81 on `lotka_volterra`). The median
  is 0.024 % of gradients.
- Every centered eight schools and `accel_gp` cell failed in both arms, as in
  WP43.

### Funnel

The funnel is P(omega < -5) against the exact 0.0478. The uniform arm uses the
house starts, and best_of_16 the best of 16 candidates from uniform(-3, 3)^10,
as in WP43.

| arm | z by seed 952201 / 952202 / 952203 | estimates |
|---|---|---|
| uniform | +0.77, -1.13, -0.60 | 0.0528, 0.0392, 0.0434 |
| best_of_16 | +1.11, -0.46, -0.20 | 0.0586, 0.0438, 0.0458 |

## Predictions

| | prediction | observed | held |
|---|---|---|---|
| P1 | geomean >= 1.10 | 1.254 | yes |
| P2 | best_of_16 credited >= uniform | 42 vs 42 | yes |
| P3 | funnel abs z <= 2, both arms, every seed | max 1.13 | yes |
| P4 | uniform: minor-mode chain and R-hat > 1.01 on >= 2/3 seeds | 3/3 | yes |
| P5 | best_of_16: all chains major and R-hat <= 1.01 on >= 2/3 seeds | 0/3 | **no** |

P5 failed as the agent's design calculation said it probably would
(probability about 0.11). The rule's safety clause F4 was close to a coin flip
before the run (about 0.47 to trip). It did not trip, partly because warmup
moves chains between modes 8 SD apart.

## Reading

- **What the rule measured.** Best-of-16 removes the gross start lottery.
  Starts at log density -1e115 or -3e4 that freeze a chain on `arma11` and
  `lotka_volterra` are gone. Over WP43 and WP52 combined it fixed 4/4 such
  uniform failures and created none of that kind. Its two-mode bias is real
  (single-basin four-chain starts 12.8 % to 22.7 %) but did not hide a mode on
  the three sampled seeds.
- **What the rule did not price.**
  1. **The 14 healthy models lose.** They are at 0.862x here and were 0.967x in
     WP43. The 0.862 is dominated by one lost `earnings` cell (0.208x on that
     model) and centered eight schools (0.524x, failing in both arms). Without
     those two models the other 12 are 1.01x. The cost is driven by cells, not
     uniform, but it is not zero.
  2. **The `hmm_drive_0` second-mode chain moved arms.** Over WP43 and WP52,
     uniform had 1 visible R-hat failure on `hmm_drive_0` in 8 seeds, and
     best-of-16 had 1 hidden-mode cell. A visible failure is safer than a
     hidden one. Only `chain_warnings` (WP44) caught it, which supports
     recommending `chain_warnings` as part of the default diagnostic reading.
- **Credited passes.** Pooled over 136 cells across both studies, uniform has
  113 and best-of-16 114: a tie in gates. The efficiency headline comes from
  two models.

## Recommendation

1. **Library.** The frozen rule says flip, and the flip is implemented on
   `wt/init-confirm`:
   - `Init::default()` is `Init::best_of(16)`, with the new constant
     `DEFAULT_INIT_CANDIDATES`.
   - `run_from_random_starts` uses `Init::default()`.
   - The docs, README and CHANGELOG are updated.
   - A new pinned fingerprint of the default start rule is added in
     `tests/kernel_fingerprint.rs`.

   The kernel fingerprints are unchanged because they use explicit starts.
   `ALGORITHM_REVISION` is not bumped, following the precedent of the
   `DEFAULT_U_TURN_RULE`, `DEFAULT_METRIC_REGULARIZATION` and
   `DEFAULT_CHAIN_RESCUE` flips: the walnutpie kernel, `RunConfig` and draws
   from given starts are bit-identical. Only the starts drawn for a given seed
   change. `cargo test` is green.
2. **Before merging,** the coordinator should decide whether a hidden-mode
   cell on a real posterior is acceptable under a rule that did not gate on
   it. If not, keep the WP43 opt-in and revert the last commit on this branch.
3. **Either way,** document that `chain_warnings` is the instrument that caught
   both arms' failures here.

## Files

- `PREREGISTRATION.md` and `protocol.json`, frozen at `f8f1b0b4`.
- Harness, reused from WP43 with arms renamed and `chain_warnings` recorded:
  - `src/main.rs`, the posteriordb cell;
  - `src/bin/funnel.rs`;
  - `src/bin/two_mode.rs`, the new safety target;
  - `run_confirm.py`, the driver and analysis;
  - `checksums.py` and `CHECKSUMS.sha256`.
- Artifacts:
  - `artifacts/cells/*.json` (102 cells);
  - `artifacts/funnel/*.json` (6);
  - `artifacts/two_mode/*.json` (6 cells and 2 start tallies);
  - `artifacts/summary.json`;
  - `artifacts/results-table.md`, covering every cell;
  - `artifacts/run-log.txt` and `artifacts/analyze-log.txt`;
  - `artifacts/measured_on.json`.

  Raw draws are in `artifacts/draws/` and are ignored.
- Environment:
  - The study-local `.venv`: Python 3.11.16, ArviZ 0.23.4, BridgeStan 2.9.0,
    posteriordb 0.2.0.
  - The models were **copied** from the sibling build
    `C:/dev/owalnuts-wt/dense-metric/STUDIES/dense_metric_posteriordb_v1/models/`
    (same posteriordb `28f8d3d` sources, BridgeStan 2.9.0).
  - The posteriordb reference draws were read in place from
    `C:/dev/owalnuts-wt/posteriordb-breadth/STUDIES/posteriordb_breadth_v1/posteriordb`.
  - All three are ignored.
- The library was built from `3924b090` (the brief's base). It does not
  include main's later `d8c3cef3` BridgeStan gradient-buffer change.
- Walls are contended (sibling agents running) and are not evidence.
