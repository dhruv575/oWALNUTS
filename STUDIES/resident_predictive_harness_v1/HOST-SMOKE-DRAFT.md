# Host development smoke feasibility ? 2026-10-27

Draft only; no remote mutation or workload launched. Review and explicit parent
approval are required before execution. This is implementation/cost diagnosis,
not a fresh inference qualification or a trading system.

## Read-only readiness findings

The shared `/home/ubuntu/venv` supplies NumPy2.5.4/SciPy1.18.1 but lacks installed
owalnuts and numba. Older python_callpath_linux_v1 and
pymc_gil_free_determinism_v1 environments contain numba and native owalnuts but
both lack WarmSession and from_cfunc_functional. Their native SHA256 values are
0df313da37397d1edda2eff34d3824f637f1e09750b31beeb3cedf42ac4c90d9 and
258100254a95dfaf3385e1486552fa076cc60f18765c90d919455b7b8c2bfbdc.
Cargo exists under /home/ubuntu/.cargo/bin and maturin under the previous callpath
lane. These artifacts are not suitable for the current resident API.

A new isolated native build plus matching Python sources is necessary. No compile
runtime has been measured and no <=10-minute all-in completion can be promised.
Do not mutate a current study environment or import a mismatched Python facade.
After archives finish, stop the idle instance unless a separate bounded build
preparation is approved. A possible preparation allocation is at most15minutes
with explicit failure/timeout capture, then at most10minutes for the smoke; both
must fit the absolute instance backstop and archive reserve. This is an allocation,
not a predicted build duration. No additional instance is justified.

## Proposed exact development workload, after review and build

- One synthetic N250 window, four chains, K400, exactly four updates. Same WP96
  rho=.95, nu5 and priors. All four chains retained, no data/reference accuracy
  selection. No independent posterior reference sampling in this cost smoke.
- Freeze development seeds and commit generated-data source before transfer.
  Generate250initial observations under stationary latent SV; at new observation2
  switch true mu by+1 and innovation sigma from.2 to.4, retaining latent continuity.
  This gives one pre-change and three early post-change updates. Save the complete
 255observations, latent path, parameter schedule and SHA256. This tiny schedule
  tests the output path; it does not test adaptation, calibration or robustness.
- Explicit native tuning max_depth10, max_refinement_levels8, min_micro_steps1,
  max_error1, divergence_threshold1000, momentum_sum U-turn, stop exhaustion.
  Initial four-chain fit:1000warmup/200retained, explicit initial coordinates
  mu=2log(.005), log_sigma=log(.2), beta=0, z=0; adaptation target.8 with diagonal
  metric. Record initial fit diagnostics and mark poor initialization honestly.
  These are development settings, not WP96 best-of16 initialization reproduction.
- Resident policy frozen: exact stationary-boundary remap, old boundary mass,
  shifted remaining masses, appended innovation0/mass1, unchanged step sizes.
  Public session seed schedule, no re-adaptation, no pooling, no chain dropping.
- At every update return analytic scale P50/P95 plus full-return P5/P50/P95 from
  joint mu/log_sigma/beta/h_last; GH64/128, chunk512,64MiBcache per rule, root residual
  <=1e-8 and cross-order CDF/interval-normalized endpoint discrepancy <=1e-6.
  No node-order reduction or hidden thinning. Numerical disagreement fails the
  update and terminates smoke. Full-return posterior accuracy remains untested.

## Bounds and telemetry

An external Linux supervisor owns the process group and kills/reaps all descendants
at600seconds from Python start, including imports, JIT, initial fit, tests, four
updates and output persistence. A30second numerical deadline is subsidiary, not
a replacement for the process watchdog. The prior explicit2m evaluation ceiling
cannot admit representative depth/K. Use documented admit_worst_case=True without
that misleading explicit ceiling; record this and rely on the hard wall watchdog.
No retry or reduced-depth rerun is authorized by this draft.

Record source Git commit plus hashes for harness, numerical processor, Python API,
native extension, wheel/build metadata and model inputs. Record actual runtime
DEFAULTS and explicit tuning/adaptation configuration, Python/numba/numpy/scipy
versions, affinity, CPU model and Rust feature flags. Check the freshly built
extension exposes both resident functional APIs; import from a controlled isolated
installation, not a preexisting editable checkout.

Measure each total tick directly from new-window construction through final
validated outputs. Include target owner/remap/retarget, native refresh, compact
transport, scale and return inversion, checks and telemetry serialization into the
returned record; durable disk writing is reported separately. Preserve structured
per-chain diagnostics, effective seeds, target calls and work. Record process
getrusage peakRSS and supervisor wall/exit/timeout independently; explicitly report
whether child processes exist. Save each completed update immediately, plus terminal
failure status even on timeout. Archive raw compact draws for all four updates
without changing the original chain identity; this enables later arithmetic checks,
not an independent posterior validation.

Both1) conservative summary arithmetic alone exceeding0.4s and2) the complete tick
exceeding0.4s are useful negative findings. Do not lower GH order after seeing them.
Passing0.4s is only a four-update development observation; it cannot qualify an
AMM, validate returned probabilities or demonstrate profitability. Stop the instance
after verified artifact retrieval once all other authorized work has drained.
