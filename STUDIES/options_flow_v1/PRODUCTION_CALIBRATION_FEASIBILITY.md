# Prospective production-procedure feasibility cohort

The cohort has completed. The retained coverage artifacts in
`artifacts/production-calibration-feasibility-v1` record flow public 8/8 and
reference 2/2 usable fits, and local public 6/8 and reference 1/2. Every report
remains `qualified=false`; no coverage component met its reporting rule. These
T32 results establish feasibility and expose failures, not powered calibration.

The following describes the original prospective controller and its frozen
policy. For a new cohort, choose the recipe explicitly before invoking
`prepare`. The combined controller,
adapter/reporter, reference allocation, associative-target and mixed-worker test
run passed 55 tests and 20 subtests in 42.81 seconds on the attested Python
environment. This validates implementation contracts, not interval calibration.

The intended denominator is twenty cells: eight fresh prior-generated T32
four-group flow datasets and eight T32 local-level datasets, plus two preselected
reference fits per model (dataset indices 1 and 6). The local generator uses an
exogenous anchor of zero. Each fixture has one future observed outcome per group
(four flow forecast cells, one local forecast cell). References share the selected
dataset's canonical starts and chain/prediction seeds; all independent datasets
have distinct dataset, initialization and sampler seed streams.

Flow candidate choice is required: `noncentered` or `mixed_slopes`. Local candidate
choice is fixed to `observation_residual`. The flow reference uses the tested
optimized noncentered NumPyro recipe at target acceptance 0.9; the local reference
uses observation-residual NumPyro at 0.9. No recipe is selected from newly generated
data, truth, retained ranks, diagnostics, failures or coverage results.

The existing worker/adapter contract derives predictive seed as chain seed plus
130000. This design audits all 64 distinct seed values and records this derivation;
it does not pretend the seed selection is independently randomized. Prediction
uses a separate PRNG stream from generation and initialization.

Every fit runs the complete frozen procedure: four chains, 1000 warmup transitions,
first passing retained tier among 1000/2000/4000/8000, all canonical health checks,
all physical functionals, all observed forecasts, zero retained divergences and
endpoint MCSE/width <=0.02. CPU0 workers are contained before execution and capped
at 600 seconds per cell. Imports, compilation, runtime parity, adaptation, all
draws, diagnostics, forecasts, serialization and wrapper costs remain charged.
The sum of twenty worker allowances is 12000 seconds. This is not a global
wall-clock deadline: wrapper startup, descendant reaping, preflight and reporting
add overhead. The established hardware wrapper owns timeout and descendant
cleanup. The controller deliberately does not apply a second timeout that might
kill that wrapper before it reaps children. A stuck wrapper therefore requires
external supervision; no stronger controller deadline is claimed.

`production_calibration_feasibility.py` has separate prepare/freeze/run/report
actions. Prepare writes immutable recipe intent before importing a generator.
Freeze checks the original intent, sources/runtime, fixture identities, starts,
seed streams, full selector families, commands and procedure digests. Seed audit
evidence names the auditor and bounded search scope, with immutable searched
file paths/hashes; preparation independently checks exact seed tokens in those
files. Freeze verifies each fixture/source binding and unique contained output
paths before creating any frozen manifest. Run writes
the adapter's required protocol/procedure/fixture/dataset start marker before
launch and never retries a started cell. Failed launch, timeout, missing report
and provenance-aborted remaining cells stay in the intended denominator.

Four manifests keep models and procedures separate. The existing production
adapter independently recomputes health, precision, first-pass behavior, truth,
starts, continuation state, costs and provenance. Its normalized records feed
the existing reporter, without promoting raw worker success flags to evidence.
Each flow summary has eighteen selectors: fourteen parameters and four forecasts.
Reporting both conditional and unconditional intervals plus one usable-probability
claim requires `2*18+1=37` claims. Each local summary has six selectors, requiring
`2*6+1=13`. There are two separate summaries per model (candidate and reference),
so the common whole-family allocation is `2*37+2*13=100` claims.

The alpha 0.05, nominal coverage 0.9, illustrative tolerance 0.05, usable-probability
reference level 0.9 and eight-replicate reporting floor are feasibility reporting
settings, **not qualification requirements or a powered calibration design**.
The settings are fixed in pre-generation intent. Confidence bounds will be wide;
the reference subsets contain only two datasets; all reports remain
`qualified=false`. The sampler's 2% numerical-precision screen is also only the
declared production procedure under evaluation, not proof of calibration.

The four reference cells are diagnostic comparisons, not a reference posterior
truth bank. The cohort does not establish market usefulness, calibration,
positive alpha, broad reliability or a performance claim. An independently
designed larger cohort would be needed for any stronger inference.
