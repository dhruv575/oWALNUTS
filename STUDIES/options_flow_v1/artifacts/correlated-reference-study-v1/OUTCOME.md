# Correlated reference feasibility: integration failure

The frozen 28-cell study produced **zero completed analytic cells**: all four sentinels failed and all 24 main cells remained unstarted under the prespecified sentinel-failure rule. No accuracy, coverage, equivalence, or variance-scaling conclusion is available from this campaign.

Each sentinel reached the worker's bank-output boundary, then failed with `TypeError: unsupported operand type(s) for /: 'str' and 'str'`. The CLI supplied a string output directory to `cell_worker`, which expected a `Path` for `out / 'bank.json'`. The earlier tiny smoke used a `Path` and did not exercise this exact CLI boundary. Computation before the exception is not a completed, validated bank result and is not counted as usable evidence.

All outcomes and costs are retained: four worker failures cost **36.1727 seconds** in total; the campaign controller recorded **36.2492 seconds** overall. These are failed-workflow costs, not sampler or estimator performance measurements. No retry, seed replacement, statistical threshold change, or reinterpretation of unstarted cells was made.

`outcome-analysis-v2.json` preserves the complete denominator, reports all progression checks as false, and leaves variance comparisons empty. Inferential intervals are null because no evaluable cells completed. Intended-denominator zero fractions remain descriptive; skipped cells are not Bernoulli accuracy outcomes. The three focused analysis tests passed in **0.59 seconds**, including missing-cell rejection, unstarted alternatives, and failed-work costs. The analyzer completed without requiring nonexistent bank files for failed cells.

The next useful scientific step remains a small actual-posterior reference-bank pilot with independently checked endpoints and explicit achieved reference uncertainty. First fix the CLI path conversion and verify that exact execution boundary in a bounded smoke. This failure does not justify another automatic broad analytic expansion or a claim of posterior accuracy. Any subsequent run needs its own prospective scope and retained failure history.
