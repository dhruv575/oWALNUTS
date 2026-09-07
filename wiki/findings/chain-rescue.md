# Cross-chain rescue during warmup

## State of knowledge

The one-bad-chain failure class (`lotka_volterra` frozen on an ODE boundary,
`arma11` pinned or crawling from an astronomically bad start, `hmm_drive_0`
drawing a second HMM mode) is real and no independent-chain sampler recovers
it. Re-seeding an outlier chain from the best chain at slow-window boundaries
(`restart_from_best`) met its preregistered rule in WP33 and was the default
for the v6 benchmark, which had the strongest gate count of any run. It was
then removed: WP36 showed that the density rule fires broadly on merely late
chains and on every fresh-seed second-mode `hmm_drive_0` draw, and the frozen
classifier could not prove those actions were not destroying genuine modes.
The shipped default is no rescue. The policies remain available as explicit
opt-ins. Evidence is in the [ledger](../research-ledger-2026-08-31.md).

## Timeline of evidence

- **WP25** (`STUDIES/posteriordb_bench_v3`) and **WP27**
  (`STUDIES/step_collapse_v1`) named the failure class: `arma11`'s
  post-escape crawl at `h ~ 1e-8` (a start CmdStan also crawls on), the
  `lotka_volterra` `rk45`-boundary freeze, and `hmm_drive_0`'s start-mode coin
  flip. WP27 proposed a cross-chain restart or an init bound as the remedy.
- **WP31** (`STUDIES/joint_default_v1`) failed its no-model-below-0.85x rule
  on `hmm_drive_0` (0.005; a second-mode chain drawn on two seeds) and noted
  that every kernel change perturbs the first warmup transitions and so the
  mode draw; a cross-chain mode check at the end of warmup was named as the
  right instrument.
- **WP33** (`STUDIES/chain_rescue_v1`, preregistered before implementation).
  Eight models plus the funnel, seeds 88101 to 88103. Arms: `da` (defaults),
  `restart` (at every slow-window end a chain whose step is below 0.1x the
  chains' median, or whose median window log density is more than 3
  within-chain IQRs below the chains' median, is re-seeded from the
  largest-step non-outlier chain's window with its metric, step and dual
  averaging), `pool` (exact Welford merge across chains, median step, no chain
  moved). Rule: at least 3 more of 27 cells than `da`, no model below 0.9x per
  gradient, no new |z| above 3.5, funnel |z| within 2 on every seed.
  `restart` 25/27 vs `da` 21/27, min per-model ratio 1.00, geomean 2.72,
  funnel +0.94/-0.77/-1.02: rule met, `sampler::DEFAULT_CHAIN_RESCUE`
  became `restart_from_best`. `pool` 23/27, `lotka_volterra` 0.42x,
  `mesquite` 0.83x: rule not met.
- **WP35** (`STUDIES/posteriordb_bench_v6`). Full 17-model validation under
  the rescue default: 45/51 gates vs CmdStan 34 and nutpie 29, no frozen
  chain, funnel tail exact. Release rule still failed on a passing
  `one_comp_mm_elim_abs` cell with max |z| 4.023 (no rescue in that cell) and
  an `sblrc` process error. Rescue telemetry: 30 restarts in 21 cells across
  nine models (21 log-density, nine step); 26 at transition 99, two at 149,
  two at 249. `arma11` five and `lotka_volterra` five, all cells pass;
  `hmm_drive_0` one log-density rescue on every seed and 3/3 gates, carrying
  the mode-hiding caveat; `kidiq`, `earnings`, `diamonds`, `sblrc`, centered
  Eight Schools and `accel_gp` account for the other 17, confirming
  first-boundary false positives. Funnel: four rescues, tail mass exact,
  `omega` bulk ESS 388/539/356 and two retained divergences on one seed.
- **WP36** (`STUDIES/chain_rescue_v2`). Explicit arms `observe` (scoring
  only), `current` (immediate `restart_from_best`), `two_hit` (restart only
  after two consecutive outlier hits); seven posteriordb models plus the
  funnel, 12 fresh seeds 92101 to 92112, 288 one-shot launches. Seven process
  faults (six Windows heap-corruption exits `0xC0000374`, one post-result
  timeout), six invalid paired triplets, no reruns. Paired raw-to-credited
  passes `observe` 71 to 71, `current` 74 to 71, `two_hit` 76 to 72.
  `two_hit` reduced nuisance unique-chain actions from 35 to 14 but only nine
  complete blocks remained (below the registered minimum), efficacy 1 to 0
  with nine ties, funnel full gate 4/12 with signed tail-z failures at three
  seeds, and available-case efficiency 0.893 with ARMA/HMM medians below
  0.90. `current` recorded 117 restart events, five mapped-origin overwrites
  and two unknown-origin actions (`two_hit`: 58, five, two). The frozen
  classifier found stable origins only for pathological ARMA and
  `lotka_volterra` starts and zero HMM origins. `two_hit` failed its
  conjunctive gates, the rule advanced to the `current` fallback, and
  `current` hit its mapped-origin-overwrite red lines: mechanical decision
  `no_rescue`. Commit `87d8817` restored `DEFAULT_CHAIN_RESCUE = None`.

## What worked

| change | study | result | why |
|---|---|---|---|
| `restart_from_best` at slow-window boundaries (as an opt-in) | WP33 | `lotka_volterra` 0/3 to 3/3 (289x per gradient), `arma11` 2/3 to 3/3 (crawl cell R-hat 1.60 to 1.003), controls byte-identical or 1.01 to 1.11x | Moves a frozen or pinned chain to a healthy chain's window state; costs nothing where it does not fire |
| Rescue telemetry (`ChainRescueUpdate`, criterion, source, steps) | WP33, WP35 | Every action recorded per cell | Lets multimodal users see when a chain's mode was overwritten |
| Observe-only scoring (`observe` arm) | WP36 | Identical passes to no rescue (71 to 71) | The scoring itself is free; only the action is contentious |
| `ChainDisagreement` diagnostic (leave-one-chain-out R-hat) | WP27 | Names the chain whose removal brings R-hat under 1.01 | The instrument for a mode check without acting on it |

## What did not work

| change | study | result | why |
|---|---|---|---|
| `restart_from_best` as the default | WP35, WP36 | Density rule fired on late chains at the first boundary on six ordinary models and on every fresh-seed second-mode `hmm_drive_0` draw; `current` hit its origin-overwrite red lines | A `LogDensity` rescue blinds R-hat to the mode that chain found; the classifier could not prove the moved chains were nuisance rather than modes |
| `pool_at_boundaries` | WP33 | 23/27; never moves a frozen chain (`lotka_volterra` 0/3); `earnings` lost a gate | Pooling the metric does not rescue a chain whose step has collapsed |
| `two_hit` (two consecutive outlier hits) | WP36 | Nuisance actions 35 to 14 but sample size below the registered minimum; funnel 4/12; efficiency gate failed | Fewer actions, but not enough evidence of efficacy under the conjunctive rule |
| Re-seeded `hmm_drive_0` chain | WP33 | Merged chain mixes slowly, tail ESS 398.8 | Re-seeding from a random window position of the source rather than its latest position |

## Current default

`sampler::DEFAULT_CHAIN_RESCUE = None`. Default output is tested bit-identical
to an explicit custom no-rescue warmup, with empty rescue telemetry. Explicit
observe-only, `restart_from_best`, `two_hit` and pooling policies remain
available through `Adaptation::Custom` and
`WarmupConfig::with_chain_rescue`. The retained kernel and the frozen
`walnutpie` defaults and fingerprints were never changed by this line. The
posteriordb v5 run (no rescue, 42/51) is the release headline admitted by its
own rule; v6 (45/51 under the temporary rescue default) is reported beside it.

## Open questions

- An observe-only warning at the end of warmup, built on the `observe`
  scoring and `ChainDisagreement`, has not been preregistered; it would give
  users the information without the mode-hiding risk.
- A narrowly scoped step-only rescue (the step criterion alone fired on
  `arma11` and `lotka_volterra`, where every cell passed) was named by WP36 as
  the acceptable future study; the density criterion is the one that fires on
  late chains and modes.
- Candidate C (start retry at initialisation) was preregistered as deferred in
  WP33 and never measured. `lotka_volterra` starts on the ODE failure boundary
  and `arma11` starts past |logp| 4e18 are start-rule matters that rescue only
  papers over.
- WP36's origin classifier found zero HMM origins, so the question of whether
  a density rescue on `hmm_drive_0` destroys a genuine mode is unanswered in
  either direction.
