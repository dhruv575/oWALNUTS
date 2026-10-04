# Proposed twenty-replicate feasibility execution

Proposed only: no fixture generation, execution, or qualification is authorized by this file. This is a small operational follow-up to ENDPOINT_VALIDATION_PLAN.md. It does not supply reference truth or validate endpoint error merely by observing repeatability.

## Fixed targets and independent replication

Generate two regular targets prospectively using the existing simulators with `prior=False`: flow T128/G4 and exogenous-anchor local level T128. Freeze generator source, fixed parameters, dataset seeds, serialized data and hashes before any new fit. Use one predictive horizon. Flow's predictive scenario is group0 at x_next=0; local observed log price uses dt_next=1. Simulated holdout outcomes are irrelevant to computational endpoint validation and must never become reference quantiles.

For each model generate twenty independently seeded, explicitly serialized four-chain canonical start matrices. Use the existing dispersed initialization formulas, without access to latent generating truth. Every replicate has a distinct initialization seed, sampler seed and prediction seed, with prediction seed exactly sampler seed+130000 to match current evaluators. Choose seed ranges only after collision-checking the artifact inventory. Reject collisions across all stream kinds and both models. Corresponding candidate/reference arms share the same replicate fixture and starts; this is a paired comparison, so stream reuse across its two arms is intentional. Independence applies between replicates within an arm.

There are eighty cells: two models × twenty replicates × two arms. Alternate candidate/reference first within each model across replicate IDs. Fix an execution order independently of outcomes. A failed first arm never prevents its paired arm from running.

## Recipes and stopping policy

Flow candidate: public PyMC noncentered model, block size32. Local candidate: public PyMC observation-residual coordinates. References: validated NumPyro continuation, matching flow noncentering/local observation-residual coordinates, target acceptance .9. The .9 choice comes from existing training failures, before these new targets are generated.

All cells use four chains and 1000 warmup iterations. Retained checkpoints are1000/2000/4000/8000. Candidate compiles once, then performs full warmup/restart at each attempted checkpoint; reference performs one warmup and appends fixed1000-draw batches with adaptation frozen. Charge all attempts. Freeze CPU mask, timeout and cache policy in the execution manifest. Keep parity-validation cost visible and use the same candidate preflight policy across replicates. This feasibility study measures uncertainty behavior; its elapsed costs are descriptive and not an isolated performance qualification.

Health remains all-coordinate/all-functional rank Rhat≤1.01, bulk/tail ESS≥400, and zero retained divergences. First-pass endpoint precision requires both MCSEs≤.02×interval width for five primary parameter functionals plus the selected observed forecast. Flow parameters: beta_bar,tau,mu_h,sigma_h,h_terminal. Local parameters: h_initial,h_terminal,h_mean,sigma_obs,sigma_rw. Both endpoints .05/.95 produce twelve primary scalar endpoints per target/arm.

Implementation issue to resolve before freezing: current continuation worker screens every reported flow functional and all forecast rows, whereas candidate flow supports named precision selectors. Add an explicit prospective reference selector option, or label a deliberately broader common stopping family in both arms. Never silently compare differently scoped first-pass rules. Forecast evaluation must also restrict the primary flow precision screen to group0, or prospectively declare that all four groups govern stopping while only group0 is primary analysis. This is a design decision, not an outcome-dependent adjustment.

## Minimal planner and executor

Use a new `endpoint_feasibility.py` rather than change existing study runners. Its planning step may import simulators only during a designated quiet window. Planning writes a draft manifest and literal fixtures; freezing is a distinct explicit step after hashes and scope are reviewed. No auto-freeze or auto-launch.

The manifest contains:

- Fixed data, predictive scenario and target hashes; generator source/parameters/seeds.
- All eighty intended cell IDs; per-replicate streams and literal starts; fixture hashes shared across paired arms.
- Worker commands, recipe/settings, exact stopping family, twelve analysis selectors including probabilities/scales, and execution order.
- Source snapshots, adapter/extension and executable/environment bindings, timeout, CPU and cache policies.
- `reference_bank: {resolved: false}` for both targets initially.

The target digest uses the adapter's exact canonical JSON contract: `{data: data_without_initial_positions, predictive_contract: frozen_definition, predictive_inputs: holdout_without_y}` with sorted keys and compact separators. This deliberately excludes generating truth and start matrices while retaining all posterior and predictive inputs. Each full fixture hash additionally binds that replicate's starts and stream provenance.

Execution verifies the frozen manifest and dependencies before and after every cell. Reserve a started record exclusively; never overwrite or automatically rerun an attempted cell. Use the existing hardware wrapper for CPU affinity and worker timeout. Save stdout/stderr, terminal return code, worker report/raw hashes, and outer invocation duration even for failures. Missing worker output is an explicit terminal outcome, not a reason to remove the cell.

Validate raw canonical initial positions against the fixture after each completed worker. Regenerate starts from the frozen initialization procedure during the separate validation stage if claiming initialization-stream attestation; until then use the adapter's honest label `declared_streams_matched`.

## Extraction and analysis

Build four analysis manifests, one per model/arm, each with exactly twenty expected IDs. Bind worker seed, fixture hash, source snapshot and settings. Settings must allow only the four predeclared terminal retained counts: either have the executor validate membership before constructing an exact extraction binding, or extend the extractor with an explicit allowed-draws contract. Do not derive permissive identity bindings from arbitrary report values.

Use `extract_cohort` to convert real worker functionals and forecast rows to normalized endpoints. Include an explicit source-bound semantic scale mapping: local state/forecast endpoints are log-price units, sigma_obs/sigma_rw are log-price increments; flow h is log variance, sigma_h is log-variance innovation scale, and coefficients/forecast use the declared fixture's model units. An estimated log endpoint must never be relabeled as price.

Run `analyze` with the fixed denominator. Report usable rate, missing/failing IDs, empirical endpoint dispersion, mean reported MCSE², variance ratio and its square root, the MCSE calibration ratio. These are descriptive point estimates at twenty replicates. Reference bank unresolved means no signed error, RMS error to truth, or qualification conclusion. A later independent bank can add explicitly uncertain reference comparisons; generating parameters are not quantile references.

Preserve worker-internal elapsed costs separately from outer process/affinity-wrapper costs. Report both totals and missing-cost IDs across all eighty intended cells. Do not add the two overlapping clocks or silently replace the full denominator with successful fits.

Predictive replay is a separate optional analysis after sampling: freeze multiple new replay seeds per saved posterior, hold posterior draws fixed, and report conditional replay variance separately. Its cost is separate from the original stopped procedure. Never subtract this variance mechanically from replicate dispersion or treat replay draws as independent posterior fits. Primary feasibility may proceed with replay explicitly absent, but cannot claim to have separated prediction noise without it.

## Before execution

Resolve the common stopping family and terminal-settings extraction contract above. Author planner/executor tests with mocked workers, bad hashes, duplicate streams, missing cells, timeout/failure preservation, and wrong-coordinate output. Test exact-control analysis separately. Generate the prospective targets only after source review and the current timing campaign ends, inspect/freeze the manifest, and obtain the parent's execution go-ahead. Twenty replicates remain feasibility evidence even if every fit passes.
