# WP68 amendments

## Amendment 1 (2026-10-26): block P re-executed after a driver configuration error

This amendment was written and committed before block P was run a second
time. It was also written before any block F or L result was analysed or read,
apart from the first progress line of each block in the live log.

### What happened

On the coordinator's correction I renamed the study from WP67 to WP68
(commit `938470bf`) with a blanket text substitution. That substitution also
renamed the driver's environment variables, `WP67_MODELS` / `WP67_DRAWS`,
to `WP68_MODELS` / `WP68_DRAWS`. The lane's `env.sh` on the box still exported
the WP67 names.

As a result, `run_study.py` looked for the compiled BridgeStan libraries in
`STUDIES/refinement_levels10_v1/models/`, which does not exist. The compiled
libraries are in `~/lanes/refinement_levels10_v1/models/`.

### Effect on block P (run 1)

All 102 cells (51 per arm, symmetric) ended within 0.0–0.1 s with the same
message: `error: No such file or directory (os error 2)`. The message comes
from `ReplicatedStanTarget::load`, before any start was drawn and before
`Sampler::run`. No draw, gradient or statistic exists for any seed.

The run-1 cells are kept unchanged in `artifacts/void-P-run1/`, with the
matching lines of `run-log.txt`. They measure the driver, not the sampler.
Blocks F (60 cells) and L (30 cells) do not use these variables and are
unaffected.

### Deviation

**Block P is run once more on the same seeds (670301–670303), in the same
order.** This deviates from "never rerun", which `wiki/methods.md` relaxes
only for a host-killed driver.

The case for treating it as a deviation rather than a failed result:

- The failure is a configuration error that is identical in both arms.
- It occurred before the sampler started, so the seeds revealed nothing.
- Recording 0/51 against 0/51 would leave clauses P1 and P2 unevaluable for
  a reason unrelated to the question.

The fix is in the lane's `env.sh` only: it now exports `WP68_MODELS` and
`WP68_DRAWS`. The harness, the driver code, the rules and the predictions are
unchanged.

If the second run fails in any cell, that failure stands as a result, and
there is no third run.
