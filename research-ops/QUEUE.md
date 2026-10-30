# Active research queue

## Active: fresh hybrid validation, policy frozen

HYBRID-VALIDATION.md freezes16 fresh seeds929300001..16 across six models and
five arms, four4-seed chunks. Prefer Fisher only when all held-out-chain
worst-direction R2>0; otherwise unchanged v4 block/auto. Seven analytic gate
checks pass locally and remotely. Hybrid pays all scores, probes and fit time.
Chunk1 terminal:168 jobs/120 stages verified;721-member archive restored. Hybrid
4/4 all targets except eight-schools0/4 (all arms); Fisher/dense GP3/4 vs hybrid4/4.
Chunk2 runs at work/hybrid02, SSH session91752. Inspect live PID/SUMMARY before
resuming; never restart from observer timeout. Chunks3/4 NOT launched.
Archive+exact-version restore each chunk before next;
reclaim only verified redundant RESULT gzip copies using reclaim_chunk_results.py.
Root floor1GiB. Previous broad/Fisher gzip reclamation freed50,304,299 bytes;
exact audits broad01-RECLAIM.json/fishercompare01-RECLAIM.json, originals retained.
After four chunks use analyze_hybrid.py for prespecified exploratory gate and
paired bootstrap intervals. A passing continuation gate alone is not goal success.

## Latest: Fisher baseline removes the apparent regression advantage

fisher02/03 both fail1/16 fixed numerical checks; preserve them. fisher04 uses
80-digit arithmetic and passes16/16 without threshold changes; exact S3 restores
verify11/12/12 members. Supplemental fishercompare01 is terminal:48 drained jobs,
24 same-pilot Fisher arms, original broad01 controls reused, not replication.
Candidate/Fisher ESS/call ratios .809 ARMA,.980 arK,.977 sblrc,.672 GARCH;
Fisher fails2/4 GP and4/4 centered eight schools.239-member archive verified.
See FISHER-NUMERICS-REPORT.md. No advantage or novelty claim from regression gains.

linearity01 completed24-cell post-hoc audit: ARMA/arK worst-direction out-of-chain
R2>.92, GARCH .088--.174, GP/eight-schools negative, sblrc one negative successful
Fisher case. See LINEARITY-AUDIT-REPORT.md; no independent validation claim.
Next freeze a target-name-free hybrid: Fisher when all held-out directions R2>0,
otherwise existing v4 block/auto policy; compare fresh16 seeds against Fisher,
v4, auto and dense. Audit storage headroom before launching larger batches.
REMAINING-INVENTORY.json records available reference-backed
small models; most remaining entries are Gaussian regressions. Wells has no
supplied reference. Goal/application/general improvement remains unproven.

## Latest: broader gate passes; cheap collapsed control qualifies

broad01 is terminal: 96 drained jobs, 72 matched stages, all six references
qualified. Candidate v4 passes continuation gate on sblrc (ESS/calls 15.40x
dense, 14.10x auto; four seeds). No observed paired loss vs auto; eight-schools
fails all arms, and 16 fallback cells exactly reproduce auto non-timing output.
458-member private archive restored and verified. See BROAD-REPORT.md.

collapsed01 is terminal and passes its frozen moment preflight: analytically
integrated beta plus 1D quadrature matches sblrc reference moments in ~13--14ms.
This weakens the application case; no IID sampler or rigorous tail bound claimed.
14-member private archive restored and verified. Both reports preserve failures.
192 redundant prior gzip copies reclaimed after archive and raw-file hash checks;
audit broad01/RECLAIM-GZIP.json. Root ~1.1 GiB free, tmpfs ~5 GiB free.

Next: repair dense Fisher baseline with factor/SVD numerics, preserving the
original failed preflight and fixed forward-error gates. Then qualify less
reducible non-Gaussian targets and fresh larger replication. Do not interpret
regression gains as a demonstrated application, generic novelty or goal completion.

## Latest: full-shape matched mechanism gate PASSES; broader validation pending

All96 jobs terminal/drained; all five arms pass16/16 fresh seeds. Curvature
ESS/total-call geometric ratio3.36 [2.61,4.15] vs adaptive dense and8.29
[5.46,13.57] vs fixed empirical covariance. Worst dense ratio .900; no universal
dominance. Matched schedule/cost/backup audits pass,423-member archive verified.
See FULL-SHAPE-VALIDATION-REPORT.md. Earnings is not an MCMC application.
Next freeze a broader nonconjugate/reference-qualified screen using the saved
inventory. Treat adaptive fallback as an explicit new policy if adopted, not a
retroactive change. Dense Fisher numerical baseline remains unqualified.
Production unchanged; general usefulness/novelty and paper completion remain open.

## Parallel baseline preflight: dense Fisher implementation NOT qualified

While fullshape02 continues unchanged, nine ill-conditioned Gaussian recovery
tests failed the initial dense Fisher numerical implementation; three invalid/
regularized-input checks passed. Tiny equation residuals can mask large forward
errors. Preserve this as implementation failure, not evidence against prior work.
See FISHER-REPORT.md and verified10-member archive. Need stable factor-based
numerics and unchanged-fixture revalidation before any model/sampler comparison.

## Historical launch: full block shape validation (now terminal)

V3 passes 47 analytic/exposed checks; prior failed geometries improve condition
proxies by2748--21056x, not performance. Preserve v2 failed gate. Preflight's
31-member archive restore verified. Fresh16-seed five-arm test runs in
metric-blocks-recovery-20261030/work/fullshape02; durable gzip copies in
evidence/fullshape02. SSH exec session34601. Inspect live controller and terminal
SUMMARY before resuming; never restart based on missing logs alone. Protocol
FULL-SHAPE-VALIDATION.md retains all previous gates, changes only reconstruction.
After completion run verify_full_shape_validation.py, analyze_full_shape_validation.py,
archive_full_shape_validation.py then exact-version S3 restore. Broader
nonconjugate tests remain required; no application or general improvement claim.

## Latest: matched curvature ablation FAILED

All 96 jobs terminal and drained. Accuracy passes: curvature13/16, empirical15/16,
fixed diagonal15/16, adaptive dense16/16, auto16/16. The frozen gate fails; no
qualified aggregate efficiency interval. Audits verify matched schedules, charged
costs and durable copies. See ABLATION-REPORT.md and 427-member evidence archive.
Post-hoc conditioning points to severely distorted pilot marginal variances.
Next test whole-block covariance shape with only a common scale, preserving
relative variances rather than replacing each independently. This is a new
hypothesis requiring analytic/exposed preflight then fresh broader validation.
Earnings remains disqualified as an application needing MCMC. Goal ACTIVE.

## Historical launch: matched staged ablation (now terminal)

ABLATION-PROTOCOL.md freezes fixed diagonal/empirical/curvature and adaptive
dense/auto arms with shared pilots and stage-two schedules. Earnings remains
only a mechanism target; direct posterior qualification is not revoked.
Controller PID421717 verified live, SSH exec session27983. Workspace
metric-blocks-recovery-20261030/work/ablation01, durable compressed per-job copies
under evidence/ablation01 with raw/compressed hashes. Inspect process and SUMMARY
before resuming; do not restart from missing progress alone. All jobs bounded.
Original 76 redundant model result copies (62,944,768 bytes) were hash-verified
against the restored S3 archive before reclamation; originals remain in tmpfs.
Next run analyze_ablation.py after terminal summary, inspect all failures/worst
ratios, archive_ablation.py, and verify exact-version S3 restore. No result yet.

## Latest: earnings direct posterior qualifies; not an application needing WALNUTS

Four independent 32,768-draw replicates pass frozen reference/exact-moment gates.
Density/gradient parity against Stan passes at 64 states; QR setup ~.00063s,
generation .0029--.0043s, zero sampling target calls. See DIRECT-REPORT.md and
verified 20-member archive. No application claim from the earlier metric signal.
Next: matched staged adaptation ablation with at least 16 fresh paired seeds,
then broader nonconjugate targets only if a curvature-specific gain survives.
Preserve the .379 worst ratio and numerical-installation failure. Goal ACTIVE.

## Latest: model screen terminal; earnings signal needs ablation/direct baseline

Original 80 jobs completed; four earnings candidate installs failed numerical
symmetry validation. Separate symmetric-inverse repair ran all 16 candidates;
all pass reference gates. Only earnings clears continuation: median 3.00x ESS/call
versus dense, but worst paired ratio .379. Kidiq/GARCH/GP do not clear the gate.
No usefulness claim. See metric_blocks/MODEL-REPORT.md and NEXT-CONTROLS.md.
Next qualify the direct Gaussian-regression posterior, then freeze a matched
staged ablation on fresh seeds. Distinguish curvature information from schedule
effects. Original and repaired raw evidence archived; production unchanged.

## Historical launch record: staged curvature model screen (now terminal)

MODEL-SCREEN.md freezes four targets, four fresh seeds and candidate/diagonal/
dense/automatic arms, with 16 additional discarded pilots. Candidate cost includes
probes and pilots. Reference qualification precedes efficiency interpretation.
Isolated BridgeStan harness built successfully (19.34s); production unchanged.
At launch/checkpoint controller PID 418558 is live; local SSH exec session 89174.
Remote workspace: metric-blocks-recovery-20261030/work/model01; durable per-job
copies: metric-blocks-recovery-20261030/evidence/model01. Do not restart based on
stale logs: inspect live process/session and terminal SUMMARY.json first.
Sequential four-thread sampler jobs bounded at 180s, 2GiB RSS, 64MiB output.
Next: finish monitoring; run analyze_models.py only after SUMMARY.json exists;
archive_models.py preserves raw jobs/source/models/reference, then S3 exact-version
restore verification. No outcomes or advantage claimed while batch is running.

## Latest: staged curvature integration passes Gaussian fidelity; dense still cheaper

Eight candidate and sixteen control replicates pass frozen known-Gaussian gates;
all 32 jobs including pilots drained. Correct matrix convention verified: invert
selector covariance before installation as momentum mass. Candidate saves calls
against diagonal, but full dense is cheaper on every correlated replicate. No
advantage claim. See metric_blocks/ONLINE-REPORT.md; 190-member archive verified.
Next: extend the staged harness to actual models and automatic controls, freeze
fresh seeds and reference-qualified functionals. Probe/pilot costs count. This
does not replace the single-run warmup handoff and does not change defaults.
Goal ACTIVE; practical usefulness and paper novelty remain unproven.

## Latest: name-free curvature preflight passes after preserved structural failure

V1 incorrectly absorbed independent coordinates into maximal blocks. V2 adds
graph connectivity and passes seven analytic plus 120 permutation checks. It
discovers all six exposed regression blocks and rejects all six GP/GARCH cells
without parameter names. No efficacy claim: freeze online snapshot/install rules
and integrate in an isolated copy, then known-target fidelity and fresh broad
comparisons with charged probe overhead. See metric_blocks/SELECTOR-REPORT.md.
Both bounded jobs drained; complete 17-member private archive restore verified.
An incomplete earlier upload is preserved and superseded. Goal remains ACTIVE.

## Latest: metric mechanism audit complete; curvature prototype next

The proposed per-coordinate R-squared block rule is contradicted: regression
coefficient coordinates themselves fail the gate. Both passive instrumentations
preserve every historical result field except elapsed time across 12 cells each.
Offline curvature instead shows stable positive regression block shape despite
changing scale; GP shape is variable and some full Hessians are indefinite.
These are exposed, named-block diagnostics, not automatic selection or efficacy.
Next: freeze and test the name-free rule in metric_blocks/CURVATURE-DESIGN.md on
analytic controls and saved states before implementing a sampler change. Preserve
the failed earlier screens; require fresh broad validation with charged overhead.

An unexplained loss of /dev/shm erased the initial raw audit. All 24 replays were
recovered from a verified 218-member baseline archive; the first analysis exactly
matches its surviving local copy. Recovery is not independent replication. Use
the dedicated metric-blocks-recovery-20261030 mount and durable per-job copies
while the cleanup cause remains unknown. Recovered evidence is privately archived:
15,554,032 bytes, 297 verified members, SHA256
b28117c3e7033cf53478771a0f7dd382bd1184832907f26f0be4935edb7de6d3.
See metric_blocks/REPORT.md and archive/S3-VERIFICATION.json. Goal remains ACTIVE;
no sampler defaults changed and no application advantage has been established.

## Latest: conditional GP approximation passes; no application advantage shown

The synthetic GP audit is TERMINAL: four global approximations fail, four fresh
conditional importance replicates pass all frozen 24-functional gates. Reference
Rhat max 1.000886, bulk/tail minima 9681/9536. Conditional ESS is 13281--13357
of 16384, Pareto k .082--.146, maximum mean error .031 posterior SD and SD error
2.15%. Full factor/conditional-solve cost is charged, not only target calls.
No matched sampler speed ranking or real-data claim follows. See gp_count/REPORT.md.

Preserve three implementation preflight failures: inspect-module shadowing,
line-search cancellation, and NumPy/Stan factor rounding. Final parity checks
pass unchanged tolerances; no production draws preceded the repairs. Eight
production jobs exited, groups drained, inputs unchanged. Archive includes all
source versions, model/data/reference, raw draws/weights and failure audits.

Per the frozen candidate logic, do not scale a GP application campaign based
on failed global Laplace: the stronger conditional baseline resolves that gap.
Next reviewed work: inspect existing retained-work counters and failed automatic
metric-selection evidence for a concrete preventable algorithm mechanism.
Any new change needs a mechanism-specific preflight and fresh broad validation;
do not promote earlier one-seed rescues, negligible allocation savings, or a
renamed baseline. Goal remains ACTIVE; no sampler defaults changed.

Concrete next audit: metric_blocks/AUDIT-PLAN.md. The current selector reduces
per-coordinate force-linearity R^2 to a global minimum. Passive telemetry must
show whether a nonlinear coordinate vetoes an otherwise useful correlated block
before any block-metric policy is implemented. Replays must preserve exact
draws/calls; exposed results cannot supply efficacy evidence.

## Latest: fixed bank repairs synthetic mixing; cheap correction is better value

Fixed-bank stationarity and both frozen oracle mechanism gates PASS. All 128
jobs are TERMINAL (17.68s), inputs unchanged, groups drained. Augmented WALNUTS
estimates true .20 region mass with RMSE .033/.039, but importance sampling
achieves .019/.021 with 800 target calls versus 115k/154k. Supplied mode centers
bypass discovery. This is not a demonstrated application or algorithm advantage;
do not scale the toy campaign. See fixed_bank/REPORT.md and verified 537-member
private archive. No default changes; goal ACTIVE.

Next: the GP count candidate's provenance is now checked (gp_count/PROVENANCE.md).
It is an 11-point SYNTHETIC benchmark, not an actual application. Historical GP
results include both passes and one common failure; dense-choice counts are not
failure counts. Freeze a bounded Laplace/defensive-importance/reference-functional
audit before any broader GP campaign. Use known cheap controls to decide whether
this target even motivates expensive inference, then strong NUTS/latent-Gaussian
controls if warranted. No new GP sampling batch has been launched.

## Latest: live-ensemble proposal correct but fails fresh mixing screen

All 128 independent-ensemble mechanism jobs are TERMINAL (28.75s), inputs
unchanged and groups drained. Known-target stationarity and restart integration
passed, but all four frozen mixing configurations failed. Cold ensembles never
found the missing region; covered ensembles estimated its mass at ~0.34 versus
true 0.20. An occupancy audit supports a last-walker reverse-proposal bottleneck.
See ensemble_moves/REPORT.md. Preserve the failed initial Lotka replay assumption:
the historical chain had escaped by its final draw. The corrected exposed
replay's early exit is mechanics evidence only, not a validated improvement.

Next reviewed task: fixed proposal bank (ensemble_moves/NEXT-DESIGN.md), first
an explicitly oracle-assisted mechanism diagnostic, then a separately costed
discovery pilot with fresh seeds if warranted. Do not omit mode-discovery cost
or use a synthetic success to claim novelty/application value. Give the same
bank to NUTS and include cheap mixture approximation before competitive claims.
Goal remains ACTIVE. No sampler/default changes. Private archive retains all
raw evidence, failures, installed modules and dependencies; originals retained.

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
