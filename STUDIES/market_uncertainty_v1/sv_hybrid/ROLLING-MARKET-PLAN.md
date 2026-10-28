# Re-adapting compiled NUTS rolling comparator

Status: adapter implementation; not frozen or admitted for market sampling.

Evaluate the same complete December, January and February rolling paths as E72,
with two fresh external seed replicates per month. Use the identical 250-return
conditioning windows, eight fixed score/retention ticks per month, pointwise
density/CDF evaluator, reference flags and causal labels. No window selection,
failed-path replacement or retry. Retain every planned path and score slot.

Compile once per path. Initial adaptation uses 1,000 warmup and 200 retained
draws; each subsequent update uses 1,000 new warmup and 400 retained draws in
four chains. Initialize around the mean of individually remapped terminal
states, then use nutpie's documented jittered initialization. New adaptation
restarts on every update; no claim of inherited chain states or metrics.

This is a practical implementation comparison against E72 K400, not an isolated
within-orbit-adaptation experiment. WALNUTS retains adapted state and consumes
400 refresh transitions, while this comparator pays for new warmup. Equal output
counts do not establish equal computational effort or fidelity. Report these
differences, actual elapsed/phase timings and available diagnostics explicitly.
Do not manufacture unavailable target-evaluation counters.

Preserve initial and sentinel full traces (including warmup), all per-update
diagnostic records, source/runtime identity, seeds, input hashes and incomplete
slots. The adapter must pass a literal end-to-end run with the existing immutable
linear evidence loop before market admission. Fit limits and the whole campaign
resource/seed plan must be frozen separately before launch. Existing E72
January K1600 failures remain unchanged; this experiment cannot repair them.

The reference cost panel already favors NUTS over the blocked specialist for
cold fitting. Rolling results must be reported whether favorable or unfavorable
to WALNUTS. Untouched predictive performance and economic feasibility remain
separate research requirements.
