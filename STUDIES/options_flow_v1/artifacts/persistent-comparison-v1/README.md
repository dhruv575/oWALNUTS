# Prospective repeated-fit development comparison

This compares two pairs of fresh processes, each fitting the same A/B/A sequence.
A is market origin 168 and B is origin 216, the earliest eligible scheduled
origins with different training observation counts. The anchored fixtures have
22 and 33 observed training cells and one eligible current forecast each.
Future outcomes do not select the fixtures, enter fitting or determine stopping.

Each process uses four chains, 1,000 fresh warmup iterations per posterior and
retained tiers 1,000/2,000/4,000/8,000. Every tier checks all 140 canonical
parameters, 14 physical functionals and the eligible forecast endpoints. The
production health and .02-width endpoint-MCSE requirements stay unchanged.
Adaptation resets for every fit. Process and compilation-cache reuse is allowed;
posterior-state carryover is not. The public path compiles each immutable target;
the reference can reuse its fixed-shape dynamic model.

The pair orders are public/reference and reference/public. Each process has a
1,800-second contained CPU-0 allowance, with all four processes and twelve fits
retained regardless of failure. Two audited initialization streams create fixed
fixture starts; six fresh sampler streams and their six prediction streams are
paired across backends. Exact choices and bindings are in the plan and audits.

The primary descriptive comparison is matched whole-process cost to three
usable fits. Report first-fit and subsequent-fit costs separately. A full-cohort
ratio is eligible only when both matched cohorts pass every fit. Valid individual
fits remain recorded in partial cohorts; all failed-process costs remain charged.
Two pairs do not establish a population speedup or general reliability.

Per-process controller clocks include launch, the worker and pre/post provenance
checks. Independent per-fit output validation and final campaign bookkeeping
occur outside those per-process clocks. A separate outer execution record must
report the entire campaign wall time so this difference is visible. No speed
comparison will silently substitute summed fit-stage time for process cost.

`seed-audit.json` preserves the original broad bounded scan. Compact audits bind
the historical RNG-declaration inventory plus that unchanged supplemental scan;
the supplemental text includes the proposed numbers by design and is hash-bound,
not incorrectly reinterpreted as historical RNG consumption. Version 2 includes
the changed tracked files since the original scan. All exclusions and encoding
limitations remain explicit.

This is an exploratory performance study on two fixed sparse-data posteriors.
It is not a market calibration study, a predictive-utility result or evidence
about arbitrary option markets. An independent prefreeze review and committed
frozen plan precede the first worker.
