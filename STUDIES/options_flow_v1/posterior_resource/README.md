# Current package status

The four-fit resource pilot has run. Both public samplers completed, but their original resource workflows failed at a report-binding adapter check; subsequent analysis of saved draws was explicitly posthoc. Those historical failures and all costs remain preserved. The adapter now checks exact attested package paths. Resource completion and numerical convergence do not establish posterior accuracy.

The package now includes a64-fit fresh-bank controller and separate bounded analysis pipeline. No fresh bank has been launched by this integration. The package integration passed108focused tests; a subsequent direct materialization regression also passes (23analysis tests total). Frozen source/input review remains required before execution.

Run module commands from the study directory (with the attested environment):

1. `python -m posterior_resource.bank_controller prepare ...`, then `freeze <run-directory>` prepares/freezes64independent fits; input streams must already be audited.
2. `python -m posterior_resource.bank_analysis_preparation prepare --fitting-plan <plan.json> --audit-path <bootstrap-audit.json> --out <analysis-directory> --seed <audited-seed>` creates the pre-fit intent.
3. `python -m posterior_resource.bank_analysis_preparation freeze <analysis-directory>`, then `link <analysis-directory>/intent.json` fixes the noncircular execution linkage. Any already-started fit blocks intent creation/freezing.
4. `python -m posterior_resource.bank_controller run <plan.json>` requires that immutable link before any fit starts and rechecks it throughout. Fitting has a6hcap,1800s/cell,CPU0/8GiB; all64outcomes remain visible.
5. After all64terminal outcomes, `python -m posterior_resource.bank_analysis_preparation materialize <intent.json>` binds existing artifacts without changing policy or selecting survivors. `python -m posterior_resource.bank_analysis_launch --plan <analysis-plan.json>` runs the separate2hphase, charging materialization, grid/cache/bootstrap and final verification. Failures or caps remain unresolved.

The frozen analysis uses the12-endpoint family, exact shared whole-fit resamples, both4k/8kprefixes, and declared common-CDF-grid numerical checks. All1012coordinate/14functional/4forecast admission gates remain required. The method retains finite-bank and estimated-quadrature limitations; it is not an accuracy certificate.

## Historical resource-pilot design notes

The remainder records the original draft and its prelaunch validation. Statements below that no pilot had run describe that earlier checkpoint, not the current state.

# T1000 actual-posterior resource pilot draft



This package prepares four fits, two/backend, on the existing dense T1000/G4 target. It does not choose streams, generate data, freeze a plan, or run a fit on import. No production seed stream has been chosen. Use explicit `python -m posterior_resource.controller prepare`, `freeze`, then `run` from the study directory actions only after review.



Recipes are public PyMC mixed slopes/block32 and NumPyro mixed slopes/associative path at target_accept .9. Every fit uses fresh four-chain initialization and1000warmup, retains exactly8000draws, and never stops at a4k precision pass. The existing workers are invoked with the sole tier8000. Prefix4000 is evaluated afterward as a declared dependent checkpoint, not another independent fit. Both checkpoints retain all1012canonical diagnostics,14physical functionals and4observed forecasts. The accuracy-analysis subset is five parameters (beta_bar,tau,mu_h,sigma_h,h_terminal) plus observed group0 forecast, each at.05/.95. This subset does not replace the full health gate.



Use the exact existing group0 next-flow covariate. Compact predictive inputs store location, future log-volatility mean and its innovation standard deviation, with Student-t observation noise included by the existing predictive-CDF routine. The16/32/64/128quadrature ladder and its numerical convergence checks remain unchanged. No substitution of x_next=0, no latent-only forecast, no alpha or dependence change, no posterior/reference qualification from numerical convergence.



Each fresh contained worker has an1800second cap spanning model imports, parity, compilation, adaptation, sampling, serialization, extraction, diagnostics and predictive integration. The controller has a7200second prospective total cap with15seconds reserved before launching further work. Allfour planned outcomes survive timeout, source failure or global-budget exhaustion. Scheduling/bookkeeping overrun is measured rather than hidden. Both backends use the same8GiB process-committed-memory cap, via the existing nested Windows memory job. Peak process memory/CPU are measured, not whole-machine or compiler-child aggregate usage; outer contained elapsed time includes child work. There is no automatic retry.



Large raw JSON is parsed once in bounded single-draw vectors into a disk-backed `.npy`. A separate compact `.npz` keeps chain/draw-ordered14functionals and predictive-mixture inputs. The original file is hashed during that same scan; prefix divergence flags are retained for public-worker health checks. Hashes bind the compact and canonical outputs. Later banks can read compact arrays without repeatedly decoding multi-GB JSON. Full-coordinate diagnostic calculations still require the canonical memmap, and raw plus binary artifacts both consume disk. End-to-end costs include the original workers' existing JSON serialization; this draft does not claim constant-memory sampling or remove output costs.



The mixed-worker adapter checks their actual distinct report schemas, normalized parity, fresh physical and sampling starts,8k policy, full diagnostic family, source/runtime bindings, CPU affinity, reference frozen adaptation and public work counters. It does not assume endpoint_replicates.extract_worker accepts these reports unchanged.



Focused tests cover: bounded extraction/hash/shape/nonfinite rejection, compact CDF equality at nonzero x_next against the existing constructor, both report schemas, early-stop/parity/state rejection, allfour lifecycle outcomes, cleanup reserve and no retry. No actual T1000 fit or pilot has run. Remaining prelaunch check: independent review and controlled actual-worker metadata/resource-wrapper smoke, then audited literal streams and source freeze. Twofits/backend are insufficient for accuracy/bootstrap confidence. This pilot informs eventual16–32independent fits/backend; it does not resolve the reference bank.





Portable integration uses package-relative imports and derives the study path from the package. The controller launches workers by module name with explicit study and attested-package import paths. Frozen plans bind the complete recursive Python package inventory as well as existing study worker sources. The Windows extension/containment requirement remains explicit; portable paths do not imply cross-platform benchmark equivalence.



Validation evidence from the original external prototype remains under `target/posterior-resource-draft`: `saved-schema-validation.json` and `saved-reference-extraction-check/validation.json`. The historical two-thousand-draw reports match the transport schema but are deliberately rejected by fixed-eight-thousand admission. A saved 240,815,717-byte reference raw file streamed to a [4,2000,1012] memmap in 2.15 seconds on the development machine, with independent first-row, predictive-location and full-file hash checks. This is an extraction check, not a sampler speed claim. No pilot fit has run.



Imports, admission, source/runtime checks, sampler work and extraction are included in the resource process elapsed clock; the memory cap is installed before NumPy/model imports. Failed phases retain their known elapsed duration. Hard termination may prevent a final worker report, in which case the outer containment record remains the cost/failure authority. Resource completion permits unhealthy posterior checkpoints or unresolved predictive quadrature: both are retained explicitly and never become accuracy qualification.

