# Active research queue

## Latest: bounded initialization rejected; exact ensemble move under review

The 78-cell bounded-init screen is TERMINAL (491.56s); all jobs exited and groups
drained, inputs unchanged. Frozen verdict FAIL: overall descriptive efficiency
1.172 and SV warmup 0.852 do not compensate for a Lotka pass loss and GP ratio
0.788. In the failed Lotka cell, bounded/unbounded samples and calls are exactly
identical because bounds never activate. The chain moves in a separate basin;
it is not a zero-movement or small-step trap. See bounded_init/REPORT.md.

Next reviewed task: implement and test the sequential ensemble independence-MH
proposal in ensemble_moves/DESIGN.md. Verify the full mixture Hastings ratio and
known-target stationarity, including a broad low-density mode, before applications.
Use independent ensembles for uncertainty; walkers within an ensemble are not
independent chains. No density-ranked rescue, no further blind bound sweep,
no default change. Goal remains ACTIVE; archived negative results stay negative.

## Latest checkpoint: 2026-10-30 qualified PK posterior, no competitive advantage

All population follow-up jobs are TERMINAL. Two independent exchange references
qualify; raw Laplace is inaccurate and the tested adaptive importance proposals
collapse to ESS about 1--2. Nevertheless matched native NUTS delivers ~1.38x the
median minimum bulk ESS/second of WALNUTS, with matching posterior means. Thus
this application does not satisfy the continuing goal. See
`STUDIES/usefulness_search_v1/population_pk/QUALIFIED-REPORT.md`.

Source correction: the old linear Stan branch was already closed form. The new
stable C++ gradient removes autodiff overhead, not numerical ODE solves. All
953 members of the combined evidence archive passed private S3 exact-version
restore verification. Preserve callback-phase ambiguity and exposed-holdout
limitations; no defaults changed. The instance remains running, root free ~1.2
GiB; work/builds remain in tmpfs with the 1 GiB root admission floor.

Next reviewed action: audit existing sampler failure and overhead evidence to
identify a concrete preventable mechanism before another implementation change.
The earlier conditional-metric candidate remains a failed screen; do not convert
its one rescued seed into a post-hoc success or repeat a broad batch without a
new mechanism. Goal remains ACTIVE; paper and research notes retain negatives.

## Continuing goal: 2026-10-29 useful application or substantive algorithm improvement

User explicitly requested continuing exploration until an actual useful case is
demonstrated or WALNUTS is improved substantively. Durable goal is active.
See `STUDIES/usefulness_search_v1/PLAN.md`; do not mark the goal complete for a
small runtime change, exploratory tail discrepancy, or a failed cheap baseline.

First audit: public ODE Laplace parameter-tail probabilities differ by up to
0.10396 from the qualified reference despite accurate tested forecast means.
This is exploratory evidence for investigating calibrated uncertainty.
The 32-job corrected importance screen completed: Gaussian 0/8 passes at 4096
and 16384 draws; defensive mixture 0/8 at 4096 and 5/8 at 16384. Value-only
density evaluation costs about 1.22 seconds at the larger budget, about 3.17
seconds including worker overhead. No proposal meets the frozen 7/8 screen
gate yet. Preserve the failed serialization attempt; it is administrative,
not evidence against importance sampling. Raw evidence remains on EC2.

Budget extension completed: 16/16 jobs. Defensive importance passes 5/8 at
65,536 draws and 7/8 at 262,144 draws, with median cold worker times 6.50 and
20.73 seconds. The final failure is precision (MCSE ratio 2.148), not reference
error or density-audit failure. This meets an exploratory screen, not independent
confirmation. Deprioritize the four-parameter ODE candidate as a unique WALNUTS
application; timings are not a new randomized head-to-head comparison.

Next reviewed work: profile reverse-check overhead and establish a reproducible
exact-output performance experiment before any kernel change. GP benchmark data
are synthetic; published reference metadata report tuned NUTS (adapt_delta .99,
max_treedepth 15) with no divergences. Do not use default-NUTS failures as evidence
of a unique application. Investigate numerical conditioning before more GP runs.

Both importance batches are terminal. Their full evidence has local verified
archives, including dependency hashes against the prior ODE and screen archives.
Screen S3 exact-version restore verified; see archive-budget-v1 for the budget
restore receipt. No originals reclaimed. Last free EC2 disk 1,234,190,336 bytes;
retain the 1GiB admission floor. Instance remains running. Goal remains active.

Common-functional audit now complete: WALNUTS 6/8, NUTS 7/8. All WALNUTS
errors pass, but two fail precision. All NUTS errors and precision pass, with
one diagnostic failure. This is exploratory, not a rewritten original pilot.
See usefulness_search_v1/mcmc-audit01; 82 archived dependencies verified.
Prior WP39B already rejects untruncated reverse-check orbits as a general
improvement. Profile with kernel_bench before selecting another mechanism.

Kernel allocation screen complete (kernel_profile/REPORT.md). Eight paired
runs show unused-schedule removal helps funnel ~5% but regresses Gaussian ~3%
and leaves Eight Schools unchanged; calls/draw fingerprints match. Candidate
not adopted. Inspect larger allocation and metric costs next. Compilation and
runs used /dev/shm; originals remain, no inference jobs currently running.

Next substantive mechanism screen is now launched: late metric selection,
36 jobs, three arms (diag, auto window 2, auto window 3), four exposed models,
three fresh seeds. See usefulness_search_v1/late_metric/PROTOCOL.md. Current
root /dev/shm/late-metric-20261029, pinned Python supervisor run.py, run01.
Build succeeded with source/binary hashes in BUILD.json. Initial launch with
system Python failed before creating jobs (psutil missing); preserved launch.log.
Pinned environment launch uses launch-pinned.log. Each job has 600s/2GiB/64MiB
bounds; at most three four-core jobs. Inspect actual PID and FINAL before any
restart. This is exploratory; no default change or success claim.

CPU profiling collected 2199 samples with zero lost samples. Largest individual
symbols included diagonal kinetic energy (~7.2%), target callback wrapper (~6.6%)
and U-turn checks (~5.4%); no dominant unused-allocation mechanism. Ordinary perf
was denied by kernel policy; sudo perf collected only this owned benchmark
without changing system policy. Reports preserved under kernel_profile.

Late-metric screen is TERMINAL. Original run01 invalid: source replacement
corrupted environment key, so both auto arms selected window 2. Preserved.
Repaired fresh-seed run02: all 36 diagnostic passes, correct recorded windows,
44.30s, dependencies unchanged and groups drained. Candidate window3 fails:
geomean ESS/call vs auto2 .9468, earnings .873 (<.9 floor). Do not adopt.
Evidence and source/binaries/dependencies in verified 302-member archive.
No inference jobs remain live. Next hypothesis: conditional late reconsideration
only after early diagonal choice, retaining successful early dense decisions.
Implement actual warmup policy; never choose completed chains post hoc.

Conditional reconsideration implemented behind research opt-in, defaults unchanged
(commit ad425668). Fourteen targeted metric/fingerprint tests passed, including
exact unchanged-path draws/work and serial/parallel parity. Reserved exposed
kidiq preflight verifies late-dense candidate exactly matches window3, including
work and metric updates. Candidate runs both two-window observers and only
reconsiders after early diagonal selection; no post-hoc chain selection.

Fresh 36-job screen RUNNING at /dev/shm/reconsider-20261029/run01; last verified
14 complete, three live four-thread workers. Supervisor run.py (pinned Python),
launch.log; inspect PID/FINAL before restarting. Seeds 927100001--927100003,
three arms diag/auto2/reconsider. Frozen protocol in usefulness_search_v1/reconsider.
Disk 1,223,712,768 free, tmpfs 15.88GB free. Source/build hashes and test logs
committed; preserve complete evidence and analyze exact early-dense/final-diagonal
matches before any efficiency claim. No proven improvement or goal completion.

Conditional reconsideration screen COMPLETE: 36 terminal jobs, 11/12 diagnostic
passes per arm, 11 unaffected candidate paths exact. One kidiq recovery (~5.49x)
but median-based geomean versus auto2 1.0 <1.2: FAIL. Keep research-only, no
promotion or broader confirmation. Seventeen targeted tests total passed.
Complete evidence locally verified (218 members); S3 receipt in reconsider/archive.
No inference jobs live. Next review: population PK on preserved Theoph data,
with identifiability/numerical preflight and a simpler linear population model.
Do not assume extra dimensionality, expensive ODEs or synthetic GP establish
usefulness. Prior patient reference failures remain failures.

Population PK preflight COMPLETE (8 fits). Initial nonlinear gradient check at
1e-8 tolerance failed; fixed 1e-4 gradient-error gate passes with 1e-10 solver.
Qualified starts linear2/4, nonlinear1/4; other optimizer success flags rejected
by gradient gate. Selected modes pass tighter/alternate-solver audit. Exposed
withheld-from-fit log RMSE .2489 linear vs .5353 nonlinear, no posterior/clinical
claim. Complete 47-member archive verified locally and through exact S3 restore.
No jobs live. Next: shared native hierarchical linear target and posterior
comparison with tuned NUTS and Laplace/defensive IS, frozen functionals and
reference gates. Do not force an ODE application against the stronger simple model.

Shared native population target implemented and verified: 12 raw points agree
with Python density/gradients (<4e-15 scaled gradient error); analytic value-only
density differences agree within2e-13; whitening parity passes. Source in
usefulness_search_v1/population_pk/population.cpp and native.py. This enables
fair native WALNUTS/NUTS and gradient-free importance baselines.

Identifiability preflight finds an alternate rate-order mode. Rate exchange
is exact for nine zero-baseline subjects, not for the three nonzero baselines.
Initial overbroad symmetry assertion and false unscaled optimizer convergence
preserved; objective divided by96 finds a qualified second mode (gradient .000378).
Approximate Laplace log mass ratio -21.87 is NOT verified posterior mode mass.

Two sampler pilots RUNNING at /dev/shm/population-posterior-20261029/pilot01;
last verified workers393654(WALNUTS),393655(NUTS), supervisor393651. Four chains
1000/1000, white/.99, two starts per mode; 300s/2GiB/16MiB each. Pinned Python
run_pilot.py, launch.log. Not references or comparative validation. Inspect
FINAL/PIDs before restart. Freeze full uncertainty/calibration/validation rules
only after implementation/mixing pilot, with distinct fresh seeds. All earlier
model/preflight failures retained. No useful-application success established.

Pilot update: both TERMINAL at 77.29s (supervisor FINAL exists). NUTS54.05s,
WALNUTS75.09s; BOTH retain rate-order occupancy [1,0,1,0] by chain: no crossings.
Neither is a qualified global posterior reference. No divergence/depth hits;
callback errors NUTS1, WALNUTS598 (phase not separated). These are distinct
single pilot seeds, not performance validation. Full results still remote;
archive before further modifications. Next resolve global mode mixing and
establish a mode-aware strong baseline before expanding sampler comparisons.
Candidate mechanistic investigation: exact involutive rate-exchange Metropolis
moves (with proven Jacobian/detailed balance), or an equivalent marginalized
model. Do not claim correctness from post-hoc draw relabeling or local Laplace
mode weights. Both samplers must receive comparable model-aware controls.

## Latest completed checkpoint: 2026-10-29 pharmacokinetic ODE pilot

All 117 corrected jobs completed: 32 calibration, 14 reference, seven Laplace
and 64 fresh validation fits. Data partitions, disjoint seeds, source/selection
freezes and process drain audit passed. Four backend/numerical and three
analysis tests passed. See [conclusion](../STUDIES/pharma_ode_v1/results-20261029/corrected/CONCLUSION.md)
and [full report](../STUDIES/pharma_ode_v1/results-20261029/corrected/REPORT.md).

Public ODE benchmark: WALNUTS 8/8 versus NUTS 7/8 qualified seeds; seven matched
pairs give 1.65x kernel speedup [1.58,1.73] and 1.61x cold-total speedup.
The full practical-success rule fails: Laplace meets this benchmark's tested
forecast tolerances, and all three nonlinear patient references fail the frozen
qualification gate. Patient matched-accuracy claims are unavailable, not zero
demonstrated accuracy. The simpler linear model has qualified references.

Next reviewed research task: explain reference discrepancies and freeze a new
uncertainty requirement that cheap methods genuinely miss before scaling ODE
experiments. Preserve the current primary failures; do not extend this exposed
pilot until it wins. Broader specialized-solver comparisons and clinical
decision value remain unestablished. No further inference batch has been launched.

The instance remains running. Last verified free disk: 1,413,148,672 bytes.
AWS login was renewed with user permission; current-client /32 SSH access was
restored without changing the instance role. Both legacy and corrected evidence
have verified local archives (314/550 members); exact-version S3 restore receipts
are stored alongside them. Retain originals and reclaim only verified redundant
copies when preparing the next bounded job. Entries below are historical notes,
not live running status or current AWS authentication status.

### Historical launch and repair notes

Current running root is `/home/ubuntu/lanes/pharma-ode-logforecast-20261029`.
The original 53-job batch completed but 32 forecast evaluations crossed zero
numerically. Its complete 314-member archive is verified locally (SHA256
`693ba95f5b5cf483125c2c6adf1d3c477d99eaeafff9e859d516e914aa605242`).
The separately frozen repair integrates log concentration for predictions;
training likelihood/gradients are unchanged, checked against the old native
binary. Four numerical/backend tests pass. All 53 initial jobs are rerun, then
a bounded workflow freezes calibration-only selection before 64 fresh fits.
Read WORKFLOW-STATUS.json and live run STATUS; no winner is established yet.

User authorized the practical follow-up. Frozen protocol and common native
BridgeStan adapter are in `STUDIES/pharma_ode_v1`. Three backend/solver tests
passed, including independent integration, gradient checks and both samplers.
Initial batch: 32 calibration fits, 14 reference fits and seven Laplace controls.
Then freeze calibration-only selection for 64 fresh-seed validation fits.
Observed Theoph subjects 1–3 are chosen by ID; final two measurements held out.
Public Stan fixture is a computational benchmark of unverified clinical origin.
Compare nonlinear ODE to exact linear elimination; no clinical/business claims.

Root `/home/ubuntu/lanes/pharma-ode-20261029`. Twelve exclusive cores, 900 seconds
per job, 1 GiB RSS and 64 MiB output caps, 1 GiB free-disk admission floor.
Reclaimed 528,659,221 bytes of three redundant transfer archives after matching
remote/local/restored SHA256 and reading every local tar member. Originals and
local backups remain. Receipt in the new study; local AWS login still expired.
Prior storage entry below is historical. Verify live STATUS before reporting.

## Latest checkpoint: 2026-10-29 measured likelihood-cost advantage

Completed 80 primary fits, 16 analytic IID controls, and 24 fresh-seed depth11
follow-up fits. See [report](../STUDIES/likelihood_cost_v1/results-20261029/REPORT.md).
The depth10 primary rule fails because full WALNUTS qualifies 6/8 seeds.
At depth11, all three full-likelihood arms qualify 8/8 fresh seeds; WALNUTS is
1.93x faster than diagonal NUTS and 2.56x faster than low-rank NUTS in matched
native kernel time (1.82x/2.40x cold totals). This supports a controlled
cost mechanism. Analytic collapse, reparameterization and IID sampling are
much faster, so this is not a practical regression or AMM uniqueness claim.

Next scientific question: does the advantage persist for an expensive curved
posterior without an analytic shortcut, against a qualified posterior reference
and strong NUTS/Laplace/model-rewrite baselines? Freeze a representative target
and reference qualification plan before running. Do not translate this selected
Gaussian construction directly into business or profitability claims.

Storage prerequisite: last free root disk was 1,086,537,728 bytes, only about
13 MB above the 1 GiB admission floor. Do not launch another ordinary on-disk
campaign until durable archive/reclamation creates headroom. S3 remains pending
renewal of the expired local AWS login; do not broaden the EC2 role. Current
backup is streamed locally and originals retained. A redundant pivot transfer
tar was removed only after rechecking its matching local/remote SHA256.

Root `/home/ubuntu/lanes/likelihood-cost-20261029`. The instance remains running.
Entries below are historical; they are not live running-job status.

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
