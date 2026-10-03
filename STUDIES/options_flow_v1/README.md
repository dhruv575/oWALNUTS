# Options-flow uncertainty workflow

Status: **development and exploratory validation; no qualification result yet**.

The objective is to establish whether oWALNUTS makes a demanding uncertainty
estimation workflow materially easier or faster, and improve the implementation
where evidence identifies a remediable gap. Synthetic success alone does not
establish real-market usefulness or forecast calibration.

## Required evidence

1. A documented generative model and independent Rust/JAX density and gradient
   agreement, including transformed-coordinate Jacobians where relevant.
2. Simulation-based calibration of parameters and decision-relevant functionals,
   with effective sample size, Monte Carlo uncertainty, and failures retained.
3. Matched oWALNUTS/NumPyro runs on identical observations, physical starting
   states, precision, chain counts, and declared compute budgets. Report both
   default-use and any tuned configurations separately.
4. Chronological held-out predictive evaluation, including interval coverage,
   width, predictive scores, and Monte Carlo error. Synthetic and real-data
   results must remain explicitly distinguished.
5. End-to-end timing that distinguishes build/compilation, initialization,
   warmup, retention, and predictive summarization where measurable; no
   comparison of fused target calls with leapfrog counts as identical units.
6. A reproducible user entry point, input schema, provenance, actionable failure
   reporting, and runnable examples requiring no hand-written gradients.
7. If a performance or reliability gap remains, diagnose it, implement a
   justified candidate, and confirm it on fresh qualification data/seeds without
   relaxing accuracy gates. Core changes require oracle/fingerprint regression
   checks and appropriate existing difficult-target controls.

## Initial model

The first target is a hierarchical Student-t regression with shared latent AR(1)
log volatility. It combines cross-group flow coefficients, uncertain hierarchical
scale, and a long volatility path coupled to global location and innovation scale.
The initial fixed degrees of freedom and persistence are deliberate model
restrictions, not evidence that real options flow follows this model. The exact
contract is recorded with the implementations.

The initial estimand is a future observation conditional on supplied flow
covariates. Future covariates must either be available at forecast issuance,
declared scenarios, or integrated over a forecast model. Realized future flow
cannot silently be used as a tradable forecast input.

Parameter intervals here are Bayesian posterior credible intervals. Future
observation intervals additionally integrate latent evolution and observation
noise. Neither is automatically a frequentist confidence interval: repeated-data
coverage and real held-out performance are separate empirical checks.

## Application connection

The sibling `optionsWALNUTS` application contains an option-price local-level
model and chain-snapshot ingestion. Read-only inspection supplied a separate
local-level fixture with an independently checked implementation. Option-chain snapshots, minute prices, and
signed order flow are different datasets. A real options-flow validation track
requires timestamped observations with documented information availability;
neither the synthetic generator nor the sibling application's name proves that
such data is present.

## Evidence discipline

Development/pilot seeds and outputs are exploratory. A qualification protocol
will be finalized only after implementation checks and independent design review,
then committed before qualification execution as required by `wiki/methods.md`.
No exploratory cell may be relabelled as qualification evidence. Crashes,
timeouts, unhealthy fits and missing outputs count in the result denominator.
Any subsequent protocol change must be dated and explained before affected runs.

See `DESIGN_REVIEW.md` for the independent evaluation review. This study does not
change the shipped sampler defaults merely because a candidate wins a pilot.

## Development commands

From this directory (Python with NumPy, SciPy, ArviZ, JAX and NumPyro installed):

```powershell
python -m unittest discover -p 'test_*.py' -v
cargo +1.88.0-x86_64-pc-windows-gnu test --locked
python build.py
python run.py --out artifacts/my-new-pilot --exe target/release/options-flow-v1.exe --arms numpyro-noncentered,noncentered,autodiff-noncentered --reference-script optimized_reference.py --periods 128 --groups 4 --warmup 1000 --draws 1000 --chains 4 --cpus 0 --require-attestation
```

On Linux, use the native Rust toolchain and executable without `.exe`.
Select a CPU index available to the process. Affinity constrains scheduling but
does not reserve a core. `build.py` pins Rust 1.88.0 and binds executable hashes
to the core, study, and autodiff dependency source. The density-only examples in
`src/flow_autodiff.rs` and `src/local_autodiff.rs` require no manual gradients;
their performance is measured separately from the hand-gradient arms.
Every output directory is an immutable experimental attempt: use a new path,
including after a failed cell. These commands are exploratory, not the frozen
qualification protocol. `protocol.json` explicitly lists pending design choices.

`ingest.py panel.csv metadata.json fixture.json --train-periods N` accepts a
balanced panel with `origin,group,feature_available,target_end,target_available,x,y` columns.
Timestamps require explicit timezones; target availability must include feed or
publication delay, not just the end of the target period. The metadata keys are documented in the
script. Scaling is learned only on training rows and stored for inversion.
Overlapping forecast outcomes and missing group rows are rejected; they require
a separately specified model/protocol. This adapter does not turn chain snapshots
into signed order flow. Evaluation of supplied future covariates remains
scenario-conditional unless they were known at the original forecast cutoff.

`rolling_fixtures.py panel.csv metadata.json output --window N` prepares one
held-out period per rolling origin, requiring current features and every training
outcome to be available at issuance. Each origin refits its own scaling; source
and derived inputs are hashed. `no_flow()` supplies a same-noise-model ablation
with zero flow predictors, separate from the cheap empirical baseline.
Reported forecast intervals can be inverted to the declared original outcome
units. Provenance remains declared until externally verified.

`precision_tiers.py --fixture fixture.json --out new-output --arm noncentered
--exe target/release/options-flow-v1.exe --seed 99063001 --tiers 1000 2000 4000
--cpus 0 --require-attestation` runs to an explicit endpoint-MCSE/interval-width
threshold (default 2%), charging every full restart and stopping at the first
passing tier. This is an exploratory mechanism, not a qualification shortcut.
`qualification.py` recomputes component gates against a frozen expected-cell
manifest and rejects pilot reports, missing cells, inaccurate endpoints and
unhealthy comparisons. Its output never asserts overall goal completion.

`local_level.py` separately implements the sibling application's price model.
An explicit exogenous anchor permits ordinary prior-predictive calibration;
anchoring the prior on the first observed price reproduces the application's
empirical-Bayes convention but is not the same SBC experiment. Its prediction
helper distinguishes latent value from noisy future observations and preserves
joint path dependence. Price quantiles are supported; finite price moments must
not be assumed after exponentiating Student-t log-price noise.

`python calibration_design.py --trials 100 200 400 800 1200` computes exact
coverage-equivalence operating characteristics. The initial example asks for
90% coverage within five percentage points with simultaneous bounds over six
functionals: 100 or 200 independent replicates cannot establish equivalence,
and 800 have about 94% per-functional power at exact calibration. This is a
planning calculation, not an achieved calibration result; joint all-functional
power and the selected calibration scope still need a frozen decision.

## Writing a density-only model efficiently

The public Python routes are measured separately. `python_callback.py` uses
`owalnuts.from_jax` for the flow and local models; `pymc_workflow.py` expresses
the local model in PyMC and uses its generated gradients through the existing
Numba cfunc adapter. Run them in an environment containing the source-built
Python extension and their optional dependencies. PyMC's `--tiers` option
compiles the target once and charges every full sampling restart. The independent
`continuation_precision.py` reference instead reuses frozen NumPyro adaptation
across retained batches. These execution policies are explicit in results;
neither failed precision check becomes a speed win.

`breadth.py plan spec.json output` prepares 24 independent prior-generated
T=128 datasets per model, with optional six preselected reference checks per
model. It launches no sampling. Flow fixtures require independent dataset,
chain and initialization seeds and contain four dispersed canonical starts.
`breadth.py run output` executes the frozen exploratory plan;
`breadth.py summarize output` retains missing and failed cells in the expected
denominator. Source and binary changes require a new plan. This small screen
checks feasibility and failure modes, not powered calibration equivalence.

Start with `src/flow_autodiff.rs` or `src/local_autodiff.rs`: implement the
generic `Model::log_density<S: Scalar>` and wrap it with `AutodiffTarget`.
Keep the statistical model explicit, including normalized priors and coordinate
transforms. The adapter computes gradients; a handwritten target is unnecessary.

Distribution primitives accept vectors and accumulate their derivatives in a
single tape operation. Prefer one call over a vector of observations sharing
coefficients to a call for every row. For hierarchical regressions, grouping by
coefficient can be better than flattening the entire panel: the existing `Linear`
operand represents `alpha + beta * x` inside the likelihood without constructing
two scalar tape operations per observation. The flow example uses this pattern:

```rust
let x: Vec<S> = predictor_column.iter().map(|&v| S::from_f64(v)).collect();
lp += student_t_lpdf(
    Data(observation_column),
    nu,
    Linear::new(alpha, beta, &x),
    &scales,
);
```

Cache the observed columns when constructing the model, compute shared scale
vectors once per evaluation, and use existing vector transforms such as `cumsum`
for random walks. This is ordinary density code using library primitives;
model authors do not supply primitive derivatives. Parameterization still
changes posterior geometry, so fewer tape nodes alone do not establish a better
sampler configuration.

`--bench-eval data.json autodiff-noncentered 1000 result.json positions.json`
measures five blocks of 1,000 fused density/gradient calls. The optional positions
file contains an array of canonical centered positions, preferably saved posterior
draws; omitting it uses a deterministic sampler initialization, not simulation
truth. The result includes cold-call cost and tape statistics. Keep CPU affinity,
compiler provenance, and input positions fixed when comparing implementations.

In the exploratory T=1,000 fixed-position experiment under
`artifacts/target-eval-v1`, replacing per-row likelihoods with grouped `Linear`
likelihoods reduced mean target cost by about 1.93x and tape nodes from 17,023 to
7,031. Hand-gradient parity tests passed. These measurements concern target
evaluation only; posterior health, endpoint precision, and complete workflow
timing must still be checked in paired sampling runs.
