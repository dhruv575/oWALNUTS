# DRAFT: 32-stream prior-predictive implementation/calibration validation

Status: proposal only; no data generated, no outcomes computed, no sampler/AWS
work authorized by this document. Parent review, implementation/independent-engine
preflight and a final immutable protocol/source/seed freeze are required first.
This matched-model synthetic study tests calibration and implementation under a
known model. It cannot establish market value because SV is the generator.

## Fixed design and causal indexing

32 independent streams, IDs0..31. Each draws mu~N(2log(.005),1),
log_sigma~N(log(.2),.5), beta~N(0,.002), with rho=.95,nu=5 fixed.
No truncation, rejection, favorable-parameter selection or regeneration. Let
h[0]=mu+exp(log_sigma)*z[0]/sqrt(1-rho²), then stationary AR1 recurrence;
y[i]=beta+exp(h[i]/2)*t5[i]. Generate exactly283 latent states and returns per
stream, plus immutable truth metadata, from its one reserved data seed. Parameters,
Gaussian innovations and Student-t innovations use that stream RNG in a frozen
specified order (parameters first;283 normals;283 t5 innovations). Generation
implementation must freeze NumPy version/bit-generator and exact call order.
Overflow/nonfinite hard cases are preserved as generation failures, never replaced.

Initial fit sees y[0:250] only. At update j=1..32, observe y[249+j], shift to the
latest250 observations y[j:250+j], and forecast y[250+j]. Thus scored labels are
y[251]..y[282]; y[250] is the first newly observed update value. Generate the extra
label y[282] before any evaluator may accidentally truncate the last forecast.
No tick0 forecast is scored. Exactly1024 planned scored stream/update pairs.

The privileged oracle knows true(mu,log_sigma,beta) AND current h[249+j], then
integrates the next Gaussian innovation. It must NEVER use future h[250+j] to
score y[250+j]. Its better information makes it a diagnostic benchmark, not the
posterior predictive conditioned only on returns and not a required pointwise
winner. Forecasting code receives no truth values. For each fixed250 window,
the marginal stationary prior/generator matches the target, even though previous
windows share the same stream parameters. Exact posterior predictive PIT is
marginally uniform under this prior-predictive design; within-stream PITs are
dependent. Finite warm approximation and numerical error are what this checks.

## Frozen inference candidate

Resident fixed-windowK400, four chains, original boundary remap/append innovation0
and appended mass1, no pooling/re-adaptation. Same target and priors as resident
prototype. Initial fit1000warmup/200retained, deterministic prior-center positions
mu=2log(.005),log_sigma=log(.2),beta=0,z=0. Tuning: macro step.5,depth10,
refinement8,minmicro1,maxerror1,divergence1000,momentum_sum U-turn,stop exhaustion.
Initial adaptation target.8, diagonal mass, Stan metric regularization, step/mass
adaptation true. Preserve the existing default trapped-chain guard as a declared
initialization algorithm (not an ad-hoc rerun): its starts/seeds/cost and whether it
fires must be recorded. No extra initial-fit attempts, dropped chains, replacement
streams or changed seeds. One initial base and one resident base per stream.
Any terminal error poisons/stops that stream; remaining ticks become unattempted.

The sampler policy and evaluator must be independently reviewed before freezing.
Retain every four-column joint compact draw, native diagnostics, state/target
identity, seeds, timing, and per-stream hashes. Record warm/posterior diagnostics
without introducing an outcome-selected exclusion gate.

## Observed-return evaluator and endpoints

Use wp97's separately validated evaluator for posterior predictive CDF and logpdf
at the next observed return, integrating the next latent innovation and t5 noise
with unchangedGH64/128 numerical corroboration. No quantile root finding.
Density must include inverse-scale Jacobian and stable logsumexp over positive
quadrature/posterior weights. CDF/logpdf tolerances, overflow policy, independent
integration fixtures and exact implementation hashes must be frozen before data.
They are a blocking prerequisite; this draft does not invent thresholds for an
unfinished evaluator. Keep all joint(mu,log_sigma,beta,h_last) draws.

Calibration summaries: PIT mean/second moment; empirical CDF discrepancies at
p=.05,.10,...,.95; ten fixed equal-width PIT bins; lower/upper5% tail frequencies.
Report all as diagnostic estimates with uncertainty, not19 independent pass tests.
Primary predictive score summary: mean negative logpdf (lower better), with paired
stream-level differences versus the privileged oracle and a frozen cheap causal
baseline. No clipping PITs or logpdfs to improve plots/scores. Exact0/1 PITs are
retained and counted; nonfinite logpdf is a failure, not silently floored.
No market-utility conclusion from beating a misspecified cheap baseline under SV.

Cheap baseline proposal: unchanged Normal–inverse-gamma lag-return regression
hyperparameters a0=3,b0=.0002,coefficient covariance100s²I. Within the same250-return
window use249 pairs X=[1,y_previous],targety_next, training-only lag scaling; predict
at the latest observed return. This uses no extra pre-window observation. Record
this249-pair matched-information choice rather than calling it the older256-origin
historical baseline. Exact Student-t predictive CDF/logpdf includes parameter
uncertainty. Its implementation and indexing need fixed fixtures before freeze.

For uncertainty, average each endpoint over32 updates within each stream, then
use32 independent stream summaries. Report point estimates and95% stream-cluster
bootstrap intervals from10000 resamples of entire streams using its reserved
analysis seed. For vector PIT ECDF show simultaneous bootstrap sup-norm envelope
on the19-point grid as descriptive calibration diagnostics; center resampling
around the empirical mean, then compare uniform target explicitly. Do not use
1024 iid binomial trials or resample individual ticks. Also show stream-level
values and leave-one-stream-out sensitivity; do not remove hard streams. With32
clusters uncertainty can remain wide; no omnibus qualification decision is proposed.

## Failures and full denominators

Always report32 planned streams and1024 planned ticks. Categorize generation,
initial-fit, native refresh, numeric evaluator, missing-artifact and resource-cap
failures separately. Subsequent unattempted ticks remain distinct but count in
availability denominator. For PIT/logscore, publish conditional-valid summaries
with exact numerator/denominator and failed-stream IDs. A complete all-origin mean
logscore is undefined if any required score is missing/nonfinite; do not fabricate
finite penalties or claim calibration from the surviving subset. No success claim
unless all intended data and forecasts are valid under the frozen rule. Reference
failure does not delete the candidate forecast or its realized-label score.

## Sparse independent posterior corroboration (availability not yet established)

Eight fixed sentinels: (stream,tick)=(0,1),(4,32),(8,1),(12,32),(16,1),(20,32),
(24,1),(28,32). One independent-engine fit per exact latest250-return target, no
selection by PIT, parameter difficulty, candidate diagnostics or score. Tentative
budget four chains,2000warmup/4000retained per sentinel, no retries, all chains
retained. Freeze precise engine/init/adaptation and diagnostics after availability
preflight, before stream generation. Reference failure is recorded against8 planned
fits, not replaced. Spot checks cannot certify all1024 posterior approximations.

Candidate reference source exists: WP88 `models/sv.stan` represents the same
unconstrained(mu,log_sigma,beta,z) target and `run_cells.py:stan_arm` demonstrates
CmdStanPy/nutpie APIs. HOWEVER the old driver writes only(mu,log_sigma,h_last)
without beta, grows N+t rather than fixed windows, and uses default fit settings;
it cannot be reused unchanged. Current local pinned Python workflow env has no
installed nutpie,cmdstanpy orbridgestan metadata. Thus no independent fit is promised.
Before freeze: select available engine, inspect its actual installed API, validate
full target/log-gradient parity on fixed source-only fixtures, explicit four-chain
seed semantics and all four compact components, runtime identity and bounded
fit support. No installation/build/sampling is authorized by this draft.

Reference diagnostic proposal to freeze after source/API verification: finite
all-chain draws; zero retained divergences; rankRhat<=1.01 and bulk/tailESS>=1000
for mu,log_sigma,beta,h_last and observed-return CDF/logpdf functionals. Compute
functional MCSE and candidate/reference discrepancies with both uncertainties;
reference MCSE targets .005 absolute CDF and .01nats logpdf. No data-dependent
reference extension or chain dropping. Report diagnostics even when these fail.
Independent engine agreement is inference corroboration, not predictive calibration.

## Seeds, execution and cost: not yet executable

A separate audit manifest enumerates all32 data/initial/resident bases, all32x32x4
public warm chain input seeds and their splitmix64 effective seeds, initialization
chain seeds, automatic trapped-restart/candidate-start seeds,8 reserved independent
reference slots and one cluster-bootstrap seed. Check all main/active worktree
source/artifact histories before any generation. Engine-specific reference seed
mapping remains unvalidated and must be completed before final freeze. Never
claim unknown hidden/dynamic seed formulas were proven collision-free by grep.

No AWS action or sampling now. A later execution plan must give fixed process-group
caps and archive reserve, serialize cost measurements, and retain every failure.
Observed host ordinary initialization~2.15s and K400 refresh~.24s imply nominal
~69s initialization+246s native updates for32streams, before observed-return
arithmetic/references/JIT. Prior draws may create far harder cases; this is not a
wall-budget promise. Measure evaluator-only cost on frozen source fixtures first.
Independent references need a separately justified explicit budget. Do not dilute
32 streams or truncate their parameters to meet a desired success rate or runtime.

## Independent reference source follow-up

Parent supplied the more direct precedent `sv_stuck_chains_v1/run_study.py:221`:
`nutpie.compile_stan_model(code=STAN.read_text())`, `.with_data(**stan_data(N))`,
then `nutpie.sample(...chains=4,cores=4,seed=seed,save_warmup=True,
progress_bar=False,store_mass_matrix=True)`. Its `models/sv.stan` includes both beta
and generated h_last, with the required priors/rho/nu/stationary noncentered path.
This is a credible implementation route, previously used with nutpie0.16.8;
existing remote cache/package/compiler validity still requires actual verification.
The historical extraction at lines246/269 keeps onlymu/log_sigma/h_last rounded
to6 decimals, so it is NOT a usable saved-draw full-return reference as written.
New code must retain full-precision posterior['beta'] as well as all three others,
explicitly set tune/draws/adaptation rather than inherited defaults, and validate
chain/seed axes against the installed API. No reuse of rounded old output as a
precision reference. The source route reduces uncertainty about feasibility but
does not authorize a fit or promise timing/cache availability.

## Completed bounded seed reservation audit

SEED-AUDIT.json enumerates8929 distinct reserved numeric seed values, including
base/chain inputs and splitmix64/automatic-restart derivations. All six registered
worktrees returned no literal integer collisions in the bounded current
project-owned source/protocol/study metadata scan. SEED-AUDIT-SUPPLEMENT.json
separately checks the registered python-flow worktree using relative paths because
it resides beneath main's excluded target directory. Broad initial scans were
stopped as disproportionate; the completed pass used a60second shared search cap,
plus a separately bounded30second nested-worktree correction (finished quickly).

Scope includes ignored STUDIES text but excludes dependency trees, target/build/
dist outputs, binary/raw arrays, text files over2MiB and compressed archive members.
The scanner checks current decimal integer literals, not every historical Git
revision or all dynamically constructed/hex-encoded seeds. Identical source copies
were scanned per registered worktree, rather than counted as independent evidence.
This is a documented project-scope reservation audit, not a universal proof of
random-stream independence. The eight independent-engine seed slots are reserved;
engine-specific derivation/API verification remains a final-freeze prerequisite.
Reserve these exact values now to prevent another active agent from reusing them.

Reference log predictive density MCSE must target log(mean integrated density):
compute delta MCSE(mean integrated density)/mean density with appropriate chain
MCSE, using scale stabilization to avoid overflow/underflow. Mean per-draw logpdf
is a different quantity and can only be a mixing diagnostic, not a replacement
for the score or its uncertainty. This requirement applies to candidate/reference
corroboration and evaluator tests before any study data generation.
