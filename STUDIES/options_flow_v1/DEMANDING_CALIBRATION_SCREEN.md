# Demanding fresh-dataset resource screen

Status: implementation and review; no screen has been prepared, frozen or run.

The next experiment measures failure modes, full workflow costs and interval
extraction across fresh prior-generated T1000/G4 datasets. It does not establish
calibration equivalence. The completed fixed-posterior comparison passed accuracy
and reliability but missed its practical-speed criterion; see
[`RESULTS.md`](artifacts/fresh-paired-comparison-v1/RESULTS.md).

The proposed screen has 32 public cases and eight reference cases at dataset
indices 0, 4, 8, 12, 16, 20, 24 and 28. Each selected pair shares observations and
physical starts, with separate sampling and prediction streams. The controller
alternates backend order across selected pairs. Starts depend on shape, fixed
persistence and an initialization stream, not simulation truth or held-out
outcomes. Every stream must pass historical exclusion before preparation.

Use the current public mixed-coordinate block32 continuation and associative
mixed NumPyro reference at target acceptance 0.9. Both retain four chains, 1000
warmup, first-passing retained tiers 1000/2000/4000/8000, all 1012 coordinate
diagnostics, 14 physical functionals, four forecasts, zero retained divergences
and the unchanged 2% endpoint-MCSE screen. Report all 18 coverage selectors and
every failure. No failed case is replaced or retried.

`production_calibration_feasibility.py prepare --screen-spec PATH` accepts an
explicit JSON object containing `models: ["flow"]`, `periods: 1000`, `groups: 4`,
`count`, `reference_indices`, `timeout_seconds`, `total_seconds`, and `seed_rows`.
Each row specifies `model`, `index`, `dataset_seed`, `init_seed`, `chain_seed`
and `predictive_seed`; selected reference rows additionally require
`reference_chain_seed` and `reference_predictive_seed`. Prediction seeds follow
the existing chain-seed-plus-130000 contract. No new screen seeds are supplied
implicitly. Existing prepare arguments for interpreter, package, attestation,
seed audit and explicit mixed flow recipe remain required. Preparation writes
the recipe intent before generating fixtures; `freeze`, `run` and `report`
remain separate actions.

The proposed resource policy is a six-hour admission budget, 1800 seconds per
contained worker and 15 seconds reserved for cleanup. The full worker allowance
sum is 20 hours, so the admission limit may leave cases unstarted. Preserve those
cases and mark inference unresolved; a cost-dependent completed prefix cannot
be analyzed as a fixed-size independent binomial experiment. Record subsequent
normalization, hashing and reporting costs separately and add them once to the
execution total. A combined overrun also remains explicit.

Before launch, review and commit the exact protocol, seed inventory, sources,
runtime, expected IDs, storage allowance and admission policy. The shared binary
artifact utility is currently separate from the workers: its passing tests do
not change this screen's transport or permit silently changing frozen readers.

The screen informs the resource budget and computational readiness of a later
calibration study. It cannot be pooled into a confirmation after tuning on its
results. Confirmatory estimands, failure handling, error allocation and sample
size require a separate prospective decision. Existing conservative power
calculations concern worst-case completion sensitivity, not an automatically
required scientific criterion. Chronological market validation remains separate.
