# Active research queue

## Running checkpoint: 2026-10-29 dense likelihood cost mechanism

Frozen at `16be9fa1`; five validation tests passed. Eight fresh seeds across
64/2048-observation dense regression likelihoods and five arms: full WALNUTS,
two full NUTS mass settings, collapsed NUTS, and reparameterized NUTS. 80 fits
at 6,000 draws, shuffled order, 300-second job bounds, twelve exclusive cores.
Root `/home/ubuntu/lanes/likelihood-cost-20261029`; supervisor PID 371549 at
launch. Check live STATUS/FINAL receipts. Exact posterior normalization holds
geometry fixed; this tests a cost mechanism, not practical regression uniqueness.
See [protocol](../STUDIES/likelihood_cost_v1/PROTOCOL.md).

## Latest checkpoint: 2026-10-29 curvature scaling and tuning

Completed 144 calibration and 384 held-out fits, with all process groups drained
and source freezes intact. See [report](../STUDIES/curvature_scaling_v1/results-20261029/REPORT.md).
Tuning roughly halves WALNUTS fixed-budget kernel cost; hardest-case qualifying
ladders improve from 0/8 to 8/8 by avoiding depth saturation. The predeclared
multi-target speed advantage over tuned NUTS was not achieved. On dimension24,
curvature5, selected WALNUTS uses about half the target calls while wall time
remains similar; exact reparameterization is much faster.

Next research question: can reduced evaluation count produce a measured
advantage on a genuinely expensive curved likelihood? Require a qualified
posterior reference, fresh seeds, strong NUTS tuning, optimized/collapsed model
baselines, and interleaved timing. Do not use artificial delays or duplicated
arithmetic as practical evidence. Freeze that protocol before launch; it has
not yet been launched. The current additive-cost calculation is a projection.

Root `/home/ubuntu/lanes/curvature-scaling-20261029`. The instance remains
running. Verify current disk space before any next campaign; evidence backup
uses streaming to avoid a duplicate EC2 tar. Historical running entries below
are not live status. S3 remains pending renewal of the expired local AWS login.

## Latest checkpoint: 2026-10-29 known-truth geometry screen

Completed nine-geometry calibration and held-out screen, IID/Laplace controls,
16 update streams, and 96 corrected native follow-up fits. See
[report](../STUDIES/geometry_precision_v1/results-20261029/REPORT.md).
Curved banana geometry gives a precision-per-draw lead, but stronger native
NUTS controls prevent a broad computational-win claim. Original adapter
failures are preserved and corrected, not counted as algorithm failures.

Next reviewed research question: does the precision lead persist across
curvature/dimension with fresh seeds, strong native mass-matrix baselines,
and an exact reparameterization control? Specify the bounded protocol before
launch. No larger application campaign is justified by this result. The
instance remains running; completed entries below are historical. Raw evidence
is retained remotely and in the verified local archive; S3 remains pending
renewal of the previously expired local AWS login.

## Latest checkpoint: 2026-10-29 four-pivot screen

All 400 planned synthetic replicates completed in 203.49 seconds on the existing
instance; main source identity and all 3,853 archived evidence members verified.
See [results](../STUDIES/pivot_screen_v1/results-20261029/REPORT.md). Hierarchical
A/B and inventory retain modeling interest, but cheap Laplace inference captures
the observed benefit. Revenue A/B shows little separation, and logistic UCB
beats sampled Thompson policies in this short-horizon screen. No candidate yet
establishes a WALNUTS-specific decision/computational advantage. Inventory's
strict reference qualification is inadequate (NUTS 17/100, WALNUTS 26/100).

Next work should specify a narrow, independently motivated follow-up before any
larger campaign; do not simply scale this exposed screen or tune until Laplace
loses. No follow-up campaign has been launched. The instance remains running.
The completed historical confirmation also failed its frozen success rules;
see the bounded-confirmation final report. Entries below are historical and
must not be treated as live process status.

Storage: verified local raw archive `target/pivot-screen-evidence-v1.tar.gz`,
SHA256 `796c1c1260b2e4b27f5611379468ad9c384984590cbc3829b480d817798ef38f`.
EC2 originals remain at `/home/ubuntu/lanes/pivot-screen-20261029`. S3 upload is
pending renewal of the expired local `owalnuts` AWS login; no evidence reclaimed.

Updated 2026-10-28. Status requires live verification; this file is not a watcher.

1. **Running: specialist market-window corroboration.** Root
   `/home/ubuntu/lanes/specialist-market-20261028/run01`. Sixteen single-core
   workers process 192 chain slots: both methods, four chains each, all 24 E70
   windows. Five readiness tests passed in the pinned AWS runtime. Supervisor
   PID 13081 and campaign PID 13114 were observed at launch; verify identities
   before acting. Frozen manifest hash is
   `3bf02e87613e76b03a4e57f08cba86107bb839d1bac51c334037a74ee0ce7393`.
   See `STUDIES/market_uncertainty_v1/sv_hybrid/MARKET-PLAN.md` for limits.
2. **Next: terminal specialist analysis.** Preserve all 192 chains and 48
   method/window fits, all 254 diagnostic coordinates and all 24 reference
   flags. Compute actual-label predictive density/PIT with separate MCSE.
   A cold-window cost is not a matched speed comparison to E72 warm paths.
3. **E72 archived to S3.** The campaign drained: 10/12 completed, 90/96 scores,
   42/48 paired comparisons. Full local archive and 16,722 original member
   hashes verified. Two January K1600 timeouts remain. Results are committed in
   `STUDIES/warm_budget_factorial_v1/RESULTS.md`. Exact-version S3 restore
   verified all 16,722 members and both analysis reports; originals remain.
4. **Calibration and paper.** The literal independent reference completed,
   with zero divergences and all coordinate diagnostic flags passing. Both
   specialists are descriptively corroborated, with one interwoven latent flag
   retained. The raw archive is restore-verified in S3. Longer-path calibration,
   matched precision/cost comparisons and a defensible novel contribution remain
   required. Existing paper tables preserve all 44 fixed historical comparisons.
5. **Economic research.** Nine observed swaps reconcile exactly; protocol-fee
   liquidity arithmetic has five tests, but compiled-contract parity, observed
   liquidity-event replay, feasible LP controls, costs and profitability are
   unverified. Preserve negative decision results; don't select an exposed winner.

Keep the existing instance useful within limits. No deployment or trading.
Phone notifications remain about one third of the earlier cadence: batch major
scientific milestones. The last push covered independent-reference corroboration
and the pool-accounting checkpoint; do not notify for routine polls or commits.
