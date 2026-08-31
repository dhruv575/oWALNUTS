# Eight Schools v9 re-benchmark (paired re-measurement)

Frozen before execution on 2026-08-31.

## Why

The WP6 kernel correction (`ALGORITHM_REVISION` v8 → v9, endpoint energy error
instead of path-wide maximum in micro-step acceptance) changes the transition
kernel wherever refinement is active. The public Eight Schools throughput claim
in `polyscope/RELEASES/owalnuts-x-2026-08-30-v3` was measured on v7 (the v38
confirmation) and is therefore provisional.

## What is re-run

Only the oWALNUTS strict-track cells. Target, starts, four sequential chains,
1,000 warmup + 1,000 retained, target acceptance .95, depth 8, adapted diagonal
metric, one thread, tuning `h=0.3`, 8 refinement levels, `max_error=1.0`,
divergence threshold 1000, and the warm-sampler-call timing boundary are copied
from `confirmation-v38/src/main.rs`.

* Paired seeds 100070101–100070104: the v38 evidence seeds, reused on purpose
  so the comparison is paired on a frozen protocol. Not fresh.
* Fresh seeds 88001–88003 (verified unused): robustness check.
* Five timing repetitions per seed; samples must be bit-identical across
  repetitions; median wall is used, min/max reported.

Competitor numbers are cited from the frozen v3 release package, not re-run.

## Aggregation note discovered while freezing

The release text calls 19,054.65 / 14,494.34 the "conservative minimum across
seeds and six functionals". Reading the v38 `analysis-summary.json`, those
values are `summaries.rust…across_seeds.tau.bulk_ess_per_total_second.median`
and the tail analogue: the minimum over functionals of the **across-seed
median**. The true minimum over all four seeds and six functionals of the same
file is 8,634.35 / 5,949.29 (seed 100070101, whose wall was 0.255 s versus
0.09–0.11 s for the other three). Competitor minima in `validate_release.py`
are true minima over all eligible cells and functionals, so the release
compared unlike aggregations. Both aggregations are reported here for v7 and
v9 so the claim can be restated correctly.

## Gates

Health and posterior agreement exactly as v38 (see `protocol.json`). The
question: do the v9 numbers exceed every strict competitor under (a) the
release-style aggregation and (b) the true conservative minimum?

## Load caveat

Other agents are running on this machine during execution. Wall-based numbers
are therefore upper bounds on cost; ESS per target call (work-based) is the
primary robustness figure, and the paired v9/v7 ESS-per-call ratio is the
cleanest statement of what the kernel change did.
