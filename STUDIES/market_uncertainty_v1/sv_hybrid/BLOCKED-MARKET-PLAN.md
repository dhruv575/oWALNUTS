# Fixed blocked-path market panel

Status: implementation reviewed and tested; not yet admitted or launched.

Evaluate the fixed 16-state centered block update on all 24 inherited E70
windows, using four fresh chains per window, 1,000 warmup and 2,000 retained
sweeps. Keep the target, causal windows, actual labels, reference draws and
predictive evaluator unchanged. Preserve the previous 48 original/interwoven
fits, including their diagnostic failures. These are development-exposed windows;
this campaign cannot establish unseen-data performance.

The frozen manifest declares method panel [2] and all 96 chain slots. The runner
and reporter map the method identifier separately from its position in this
panel. Missing or failed chains stay in the denominator. No retries, extensions,
window selection or block-size tuning are authorized within this campaign.

Use the existing pinned runtime and 16 single-core queues. Each chain has the
existing 300-second external / 295-second internal limit, 1 GiB RSS and 64 MiB
output cap. Retain the existing whole-campaign limits and disk admission rules.
Before launch, reserve and audit 96 new external seeds, bind sources and runtime,
and verify at least 10 GiB free disk. Archive verification precedes reclaiming
redundant evidence. A source-copy test run alone is not campaign admission.

Report all 254 coordinate diagnostics, fixed R-hat 1.01 and bulk/tail ESS 400
flags, reference flags, predictive discrepancies and separate Monte Carlo errors.
Retain all 24 windows and the preexisting 22-reference-passing subset separately.
Do not infer posterior fidelity from predictive agreement alone, or economic
value from either. No speed claim is supported by unequal workloads.

Validation: 12 tests passed in the pinned AWS runtime, covering all three real
sampler transitions, block conditional-density ratios, both queue denominators,
containment failure, missing-result denominators and seed-binding rejection.
