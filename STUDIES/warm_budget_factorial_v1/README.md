# E72: paired warm-budget experiment

The post-run `inventory.py` structurally audits a drained campaign copy against
its frozen sources and E70 `COMPARISON.json`. It retains all 12 job and 96 spot
slots, checks contiguous records and retained-array hashes, and refuses an
undrained receipt. It does not calculate posterior precision or replace the
full artifact seal/restore audit. Keep this new analysis code outside the live
campaign directory; it is not part of the already frozen sampling manifest.

`analyze.py` builds on that inventory to reconstruct log(mean predictive
density) and PIT from retained per-chain arrays. It reports candidate MCSE and
reference precision separately, each seed/budget's all-reference and passing-
reference subsets, and all 48 paired-budget slots. Missing values remain in
the planned denominator. Available-case maxima are explicitly labelled;
partial-path cost is not converted into completed monthly cost. Shared seeds
and references preclude an independence-based combined-error interpretation.

Run after terminal evidence has been sealed and verified, with a new output:

```text
python analyze.py CAMPAIGN_ROOT E70_COMPARISON.json NEW_ANALYSIS.json
```

Use the pinned scientific runtime for the final analysis. Local analytic tests
check extreme log-density offsets, mixture versus mean-log scoring, missing
pairs, failed references and the sign of paired absolute-discrepancy changes.
The full result still requires campaign completion, source/evidence checks and
review; test fixtures are not scientific outcomes.

Status: running, no scientific conclusion yet. Source frozen at de91b5a6.

Partial operational checkpoint, 2026-10-28 09:23 UTC: both December K1600
paths (jobs 01 and 03) completed 1488/1488 updates and 8/8 scores, exited zero,
and drained all owned processes. Outer job times were 2778.51 and 2728.54
seconds. Their terminal receipts are in `evidence/partial-20261028/`; the full
raw campaign is still on AWS and not yet sealed. The queue automatically
started February K1600 jobs 09 and 11 while January jobs 05 and 07 continued.
This checkpoint is not a final 12-path or paired-budget result.

At the later 09:36 UTC observation, January K1600 jobs 05 and 07 had reached
their unchanged 3600-second deadlines. Both were terminated with exit -15 and
verified process drain; monitor receipts are preserved alongside the completed
December receipts. Their last started ticks were 928 and 927, which are not
claims of completed update counts. Missing terminal candidate summaries and
unreached score spots must remain in the final denominator. The queue started
December K400 jobs 00 and 02; no cap extension or failed-path replacement was
performed. The campaign as a whole remains active.
Twelve complete monthly paths compare K400 and K1600 at two seed schedules
on each of the three E66 panels. The full plan fixes data, targets, diagnostics,
reporting, retained points and resource limits before market sampling.

AWS root: `/home/ubuntu/lanes/warm-budget-factorial-20261028`.
Outer supervisor process was observed live, with four active workers 6283–6286
at first observation; these PIDs are historical identifiers, not proof of current
liveness. Verify current process identities before acting. Each worker has a
disjoint four-core affinity, and initial observed CPU was roughly 3.4–3.6 cores
per worker. No other research sampling was co-scheduled.

Read `outer-utilization.jsonl`, individual `campaign01/job-XX/candidate/progress.jsonl`
and process state for progress. Outer terminal record: `SUPERVISION.json`.
Campaign terminal ledger: `campaign01/FINAL.json`. Per-path terminal result:
`candidate/DONE.json`. A missing terminal result while the process is live is
not a failure. Never restart merely because SSH observation times out.

Two fake-engine tests passed locally. Both literal 250-return, two-update
end-to-end readiness paths passed: K400 took 5.78 seconds and K1600 took 8.75
seconds including initialization and scoring. Those toy timings are not market
cost benchmarks. Their executed pre-reservation worker copy is preserved inside
each remote literal output directory; market schedules were not used there.

The original proposed external seed range collided with two historical explicit
seeds. It was rejected before scientific sampling; SEED-REJECTION.json records
the collision. The replacement schedule reserves 34,584 unique external seeds,
with paired budget arms intentionally sharing a schedule. SOURCE-DIFF-AUDIT.json
verifies that inherited numerical code changed only its K-admission checks and
corresponding error wording. No new target or tuning rule was introduced.

At completion, retain all 12 paths and 96 planned spot scores, including missing
or failed slots. Compare to all original E70 spots with failed references flagged,
and report the passing-reference subset separately. Report both seeds rather
than choosing the better one. Whole-path accuracy, cross-algorithm superiority
and executable AMM profitability remain unestablished.
