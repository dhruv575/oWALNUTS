# Flow continuation: next isolated implementation

Status: implemented as a separate worker after the local comparison finished.
Thirteen focused workflow tests passed, including dense/masked normalized compiled
parity and an actual tiny masked worker preserving its failed health gate and
exact 4-to-8 draw prefix. No performance campaign has run. Continuation changes
execution cost; it does not repair posterior geometry or establish calibration.

## Minimal reuse

The separate `pymc_flow_continuation_workflow.py` keeps existing restart workers
unchanged. The study-only `run_session` helper accepts an optional explicit
pair of canonical-to-sampling and sampling-to-canonical functions, retaining its
current local default. Pass the existing `evaluate.summarize` as the evaluator,
with `predictive_seed` named explicitly. This reuses lifecycle, costs, frozen
adaptation checks, callback reconciliation, exact-prefix checks, immutable output,
failed attempts and cleanup rather than duplicating those mechanisms.

For dense flow, use `pymc_flow_workflow.compile_target`, `parity`,
`flow_starts.canonical_starts`, `to_noncentered` and the existing vectorized-over-
chains `pymc_flow_workflow.to_canonical`. Keep block size explicit in command,
metadata and parity binding; block 32 is a declared model-implementation choice,
not a hidden sampler default. The dense mode must reject a supplied observation
mask instead of silently ignoring it.

Defaults: four chains, one 1000-transition warmup, retained cumulative tiers
1000/2000/4000/8000, sequential public CFunc session, no change to tuning or
adaptation defaults. Keep runtime parity mandatory in the first version. A
future parity-evidence shortcut must bind the exact masked/dense target, data,
block size, software, sources and extension; do not reuse a dense evidence report
for masked data or equate a different arm label with the same target by fiat.

## Explicit masked target

Require `--model masked-flow`; validate with `masked_flow.validate` before any
target, transport or evaluation setup. Require explicit boolean observation mask
and complete regular `grid_index`. Reject observed nonfinite y/x. Compile only
through `masked_flow_pymc.compile_target`, whose observed-index gather excludes
missing likelihood contributions before residual arithmetic. Do not feed filled
data to the dense likelihood.

The strict start/transport helpers need only finite arrays for shape validation.
After masked validation, build a separate, clearly named `transport_data` copy
using zero placeholders only at unobserved entries; preserve original starts,
rho, nu and grid. Use this copy exclusively for coordinate transport. Store its
role in metadata; original data, mask and missingness policy stay bound to the
target. This is the same documented transport convention as the masked model
builder, not a missing-data inference rule.

Masked runtime parity uses independent `masked_flow.log_density` with JAX
`value_and_grad`, `noncentered=True`, plus the independent centered normalized
density at the canonical point and the NC Jacobian
`T*log_sigma_h - 0.5*log(1-rho**2)`. Validate layout `q`, dimension `4+2G+T` and
finite values/gradients. Compare starts and fixed nontruth perturbations. Tests
must cover all-observed equality with dense flow, partial missingness, arbitrary
nonfinite unobserved placeholders, all-missing likelihood, and invalid observed
entries. Never replace runtime parity with a successful compiler return.

## Health and precision contract

Reuse `evaluate.summarize`: health includes every canonical coordinate and every
physical functional, rank R-hat <=1.01, bulk/tail ESS >=400, at least four chains,
and zero retained divergences. The precision-name set is all `6+2G` functionals:
beta_bar, tau, mu_h, sigma_h, h_terminal, h_mean, every alpha_g and beta_g. With
four groups this is fourteen functionals. Enforce set equality with evaluator
output before applying the existing 2% endpoint-MCSE/90%-width screen. Do not
inherit the dense restart CLI's narrower five-name default accidentally.

Require nonempty observed predictive holdout rows and finite matching group
covariates/outcomes; reject malformed lengths instead of relying on `zip` to
truncate. Existing evaluation includes future latent process innovation and
Student-t observation noise, with fixed chain-seed+130000 per tier. Holdout masks
are not supported initially: reject them explicitly rather than score missing
outcomes as zeros. Forecasts remain conditional on supplied future covariates;
operational availability and informative observation/trade arrival are separate
unresolved modeling requirements. No qualification claim follows from a pass.

## Evidence before a long comparison

1. Mock session: one admission/warmup, increments [1000,1000,2000,4000], exact
   contiguous prefixes, strict name set, missing forecast rejection and terminal
   failure preservation. Source mutation or a mask/mode mismatch must fail closed.
2. Tiny native CFunc flow target: actual public session versus uninterrupted
   sampling at the same lifetime budget, bitwise native prefix, canonical output
   parity, nine diagnostic fields and cumulative callbacks. Compile normalized
   PyMC targets separately and run independent density/gradient parity.
3. Tiny masked end-to-end worker with explicit masked likelihood, public compiled
   target, mandatory independent runtime parity and genuine summary evaluator;
   it may fail health because it is tiny, but must complete and preserve that
   failure rather than weaken the gate.
4. Freeze a three-arm dense T1000 comparison (public restart, public continuation,
   optimized NumPyro continuation), matched starts/fixtures and declared target
   acceptance choices, all fourteen names plus observed forecasts, contained CPU0,
   exact attested release binary, all imports/compilation/parity/evaluation/output
   costs. Preserve prior outcomes and include every timeout/failure. Masked flow
   gets its own prospective experiment; it cannot inherit dense-model validation.

For a useful comparison, all three workers must share the functional-name and
forecast requirements. Existing historical five-name flow timing is contextual,
not the matched comparator for this stricter experiment. Keep serialization
optimization in a separate tested commit and bind the selected version before
freezing a new run.
