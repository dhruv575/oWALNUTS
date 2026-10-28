# Re-adapting compiled NUTS rolling comparator

Status: frozen after seven queue, seed and adapter checks in the pinned AWS
runtime; launched after verified S3 restoration and duplicate reclamation. Plan SHA-256:
`3faefcb89e13950b7c469134e098956638b832b84488313a2d9b23cb90fee02c`.
All 17,292 external seeds had no collisions in 1,357 primary historical source
records. The current seed-declaration file was explicitly excluded from that
historical scan and its hash retained; raw numerical histories were not
universally audited. The bounded supervisor started as PID 25127 on 2026-10-28.
Admission had 10,014,281,728 free bytes after reclaiming 5,982,800,906 verified
redundant bytes; restoration and cleanup receipts are preserved with the evidence.
Results remain pending.

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
resource/seed plan must be frozen separately before launch. Each path is bounded
at 3,600 seconds, 4 GiB RSS and 1 GiB output. Use four disjoint four-core groups;
the whole campaign has an 11,000-second, 22 GiB RSS and 6 GiB output bound.
Require 8 GiB free before launch and stop new admissions below 3 GiB. Output
limits are sampled checks, not filesystem quotas. Six paths reserve 17,292
distinct external sampling/initialization seeds from disjoint blocks beginning
at 705000000; audit all reserved seeds before freezing. Existing E72
January K1600 failures remain unchanged; this experiment cannot repair them.

The two-update literal end-to-end run completed both updates and scores in
20.067 seconds, including 16.540 seconds initialization. Its verified archive
contains 52 files / 58,858,523 bytes, SHA-256
`0ca471aea26ebf7a10e1aab8bd4474abc657b739e14d4cb03cbc135b644c3fef`.
Checks matched journal-to-record hashes, causal windows and label indices,
compact arrays to full-trace extracts, score-array hashes and zero recorded
divergences. This establishes evidence plumbing, not market posterior fidelity.

The reference cost panel already favors NUTS over the blocked specialist for
cold fitting. Rolling results must be reported whether favorable or unfavorable
to WALNUTS. Untouched predictive performance and economic feasibility remain
separate research requirements.
