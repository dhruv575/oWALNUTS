# E72: paired warm-budget experiment

Status: running, no scientific conclusion yet. Source frozen at de91b5a6.
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
