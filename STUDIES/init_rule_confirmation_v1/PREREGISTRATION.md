# init_rule_confirmation_v1 (WP52): preregistration

Frozen 2026-10-25, before the first evidence cell. The machine-readable copy
is `protocol.json`, and it wins on any discrepancy.

## Question

Should `Init::best_of(16)` become the default start rule? It draws 16
uniform(-2, 2) candidates per chain and keeps the one with the highest log
density. WP43 (`STUDIES/init_rule_v1`) results:

- 72 vs 71 credited passes of 85.
- Geomean min-bulk-ESS per gradient 1.258x that of `Init::uniform()`, driven by
  `lotka_volterra` 7.1x, `arma11` 3.6x and `hmm_drive_0` 3.1x. The other 14
  models were 0.967x.
- It shipped as an opt-in.

The open concern is that picking the highest-density start pulls every chain
toward the dominant mode. That could hide a multimodality that uniform starts
reveal through R-hat. WP43's screen had no target with two comparably
weighted modes, so this study adds one.

## Change under test

This study changes only the start rule. Arms, in this order:

| arm | rule |
|---|---|
| `uniform` | `Init::uniform()`, the shipped default (`uniform_starts`, radius 2, 100 attempts) |
| `best_of_16` | `Init::best_of(16)` (`candidate_starts`, radius 2, 16 candidates, 100 attempts each, `HighestDensity`) |

No library code changes before the evidence. The default flip is implemented
only if the frozen rule below passes.

## Protocol

Every cell uses the sampler at the shipped defaults:

- `Tuning::default()`
- `Metric::diagonal()`
- `Adaptation::default()`, with no chain rescue
- `Limits::admit_worst_case()`
- four threads

Every init evaluation counts in `gradients_total`. Seeds are 952201, 952202
and 952203, all fresh: `git grep -w` finds none of them, and no sibling
protocol names them.

**(a) Two-mode safety target (new, `src/bin/two_mode.rs`).** The target is the
d = 10 mixture `0.7 N(+4 e1, I) + 0.3 N(-4 e1, I)`: unit covariances, with the
means 8 SD apart along coordinate 1.

- **Placement.** The means sit symmetrically about the centre of the
  uniform(-2, 2)^10 start box. This is the only placement where uniform starts
  can reach both basins. If the major mode is nearer the box, every start
  lands in its basin. If the minor mode is nearer, both arms put every chain
  there.
- **Exact occupancy.** The major mode has weight 0.7. Its responsibility
  basin is `x1 > b`, with `b = -ln(0.7/0.3)/8 = -0.10591`, and has mass
  0.700001.
- **Mode assignment.** A start or draw is in the major mode iff `x1 > b`. A
  chain's end mode is the majority of its 1,000 retained draws.
- **Run size.** 4 chains x 1,000/1,000, three seeds per arm.
- **Recorded per cell:**
  - each chain's start, start log density and start mode;
  - its retained fraction in the major mode, its end mode, and its boundary
    crossings;
  - max and x1 rank-normalised split R-hat;
  - `ChainDisagreement`;
  - `Summary::chain_warnings` (WP44), and whether it fired;
  - pooled major fraction against 0.7;
  - divergences.

  A cell is **detected** when max split R-hat > 1.01 and at least one chain
  ends in the minor mode. A **hide event** is a seed on which uniform is
  detected while best_of_16 has R-hat <= 1.01 and no minor-mode chain.
- **Secondary tally (descriptive, not in the rule).** The start rule alone,
  with no sampling, runs on seeds 952210000-952210999. For each arm it records
  the fraction of chains that start in the minor basin, and a histogram of
  minor starts per 4-chain seed.

**(b) Funnel side check.** The target is Neal's 10-D funnel, 4 x 2,000/20,000.
The statistic is the MCSE z of P(omega < -5) against the exact 0.0478, with
|z| <= 2 on every seed. Starts follow WP43's convention:

- `uniform` uses the house starts omega in {-3, -1, 1, 3}, x = 0.
- `best_of_16` takes the highest-density of 16 candidates from
  uniform(-3, 3)^10, via `candidate_starts`.

**(c) The 17 house models.** posteriordb `28f8d3d`. The compiled models are
copied from the sibling `dense_metric_posteriordb_v1` build.

- **Run size.** 4 x 1,000/1,000.
- **House gates.** Rank R-hat <= 1.01; bulk and tail ESS >= 400 on every
  reference parameter; zero retained divergences; finite draws; no error.
- **Hidden mode (WP43 rule).** A cell that passes R-hat but whose mean is more
  than 3 reference SD off is never a credited pass.
- **Statistic.** WP43's geomean over models of the per-model, paired-seed
  geomean of min bulk ESS per gradient, taken as the ratio best_of_16 /
  uniform. The 3 lottery models and the other 14 are reported separately.
- **Also recorded per cell:** `ChainDisagreement`, `chain_warnings`, the
  per-chain reference distance, and the start log densities.

**Order.** Strictly sequential, one cell at a time:

1. (a) two-mode cells, seeds ascending, arms in order;
2. the start-only tally;
3. (b) the funnel;
4. (c) models in the listed order, seeds ascending, arms in order.

The cheap safety cells go first, so a budget overrun can truncate only the
screen.

## Decision rule (frozen)

Flip the default to `Init::best_of(16)` iff all four hold:

- **F1.** The 17-model geomean ESS/gradient ratio best_of_16/uniform is >= 1.10.
- **F2.** best_of_16 credited passes >= uniform credited passes - 1, out of 51
  cells each.
- **F3.** The funnel has |z| <= 2 on all 3 seeds for the best_of_16 arm.
  Uniform is the incumbent: its funnel is reported but not gated.
- **F4.** No hide event occurs on any of the 3 two-mode seeds.

Every protocol cell must exist. An error or timeout counts as a failure.

If the rule passes:

1. Make `Init::best_of(16)` the default (`Init::default()` and the sampler's
   default random-start path).
2. Update `tests/kernel_fingerprint.rs` if a pinned fingerprint changes.
3. Bump the kernel revision string per the `walnutpie` module docs if
   retained draws under defaults change.
4. Run `cargo test`.
5. Add a CHANGELOG entry that names this study.

Otherwise keep `Init::uniform()`, and document the negative and the two-mode
finding in `README.md` and `wiki/open-questions.md`.

## Predictions (written before running)

The coordinator's predictions:

- **P1.** The best_of_16/uniform geomean is >= 1.10.
- **P2.** best_of_16 credited passes >= uniform's.
- **P3.** The funnel has |z| <= 2 on every seed, for both arms.
- **P4.** Two-mode, uniform: on at least 2 of 3 seeds, at least one of 4
  chains is in the minor mode and R-hat > 1.01, so the multimodality is
  detected.
- **P5.** Two-mode, best_of_16: on at least 2 of 3 seeds, all 4 chains are in
  the major mode and R-hat <= 1.01, so the multimodality is hidden. If P5
  holds, F4 fails by construction. The recommendation is then "keep opt-in,
  document the trade-off".

**Design calculation (agent, before any cell).** This is a numpy Monte Carlo
of the two start rules alone on the two-mode target: 200,000 replicates, not
the Rust RNG and not the protocol seeds.

| quantity | uniform | best_of_16 |
|---|---|---|
| P(a chain starts in the major basin) | 0.527 | 0.672 |
| P(all 4 chains start major) | 0.077 | 0.204 |
| P(all 4 start major on >= 2 of 3 seeds) | | 0.108 |

These numbers assume each chain ends in the mode it started in. On that
assumption:

- P5 has a probability of about 0.11, so the agent expects P5 to fail.
- A hide event has a probability of about 0.19 per seed, so F4 trips with a
  probability of about 0.47 over three seeds. With three seeds the safety
  clause is close to a coin flip.
- The start-only tally gives the rule's actual bias on 1,000 seeds. It
  measures the hiding risk at a resolution the three sampled seeds cannot.

## Rules

- Report every cell. There are no result-driven reruns: failures are results,
  and nothing is tuned after seeing results.
- A crashed process may be relaunched, running only the cells that have no
  artifact. The deviation is recorded.
- Before the freeze, the harness was smoke-tested on seed 1, which is not a
  protocol seed. That covered one two-mode cell, one start tally, one funnel
  cell, and two `eight_schools_noncentered` cells. Their outputs are in the
  session scratchpad, are not evidence, and were checked only for exit status
  and fields.
- Walls are contended (up to six sibling agents on 16 cores) and are not
  evidence.
