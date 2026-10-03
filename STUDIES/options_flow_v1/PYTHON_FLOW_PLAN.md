# Proposed public Python flow experiment

Status: **PROPOSED; NOT FROZEN; NOT AN EXECUTION MANIFEST.** This document plans a public PyMC → PyTensor autodiff → Numba C callback → oWALNUTS route for the flow model. It records no new compilation, parity, or sampling result. Implementation and execution wait until the active frozen breadth campaign ends and a separate execution manifest is prepared and checked. The existing local-level PyMC experiment does not establish that the flow graph compiles efficiently or samples reliably.

The question is whether a user can express the demanding model in Python without writing derivatives, obtain correct intervals, and reach a fixed precision target competitively. Synthetic computational results cannot establish usefulness for real option-market decisions. See [qualification requirements](QUALIFICATION_REQUIREMENTS.md) for the separate calibration, reliability, performance, and market-utility claims.

## 1. Exact target and coordinates

Use validated immutable float64 data `y,x` with shape `(T,G)`, fixed `nu=5`, and fixed `rho=.95` for the initial experiments. Match [model.py](model.py) exactly. The sampling vector has dimension `D=4+2G+T`:

`u = [beta_bar, log_tau, mu_h, log_sigma_h, z_alpha[G], z_beta[G], z_path[T]]`.

The normalized target is defined by:

- `beta_bar ~ Normal(0,.5)`, `log_tau ~ Normal(-1,.5)`, `mu_h ~ Normal(-1,1)`, `log_sigma_h ~ Normal(-1.5,.5)`.
- Every entry of `z_alpha`, `z_beta`, and `z_path` independently follows `Normal(0,1)`.
- `alpha=.3*z_alpha`, `beta=beta_bar+exp(log_tau)*z_beta`, and `sigma_h=exp(log_sigma_h)`.
- `h[0]=mu_h+sigma_h*z_path[0]/sqrt(1-rho*rho)`.
- `h[t]=mu_h+rho*(h[t-1]-mu_h)+sigma_h*z_path[t]` for `t>0`.
- `y[t,g] ~ StudentT(nu, mu=alpha[g]+beta[g]*x[t,g], sigma=exp(h[t]/2))`.

Keep all Normal and Student-t normalizing constants. Direct standard-normal priors on `z_path` already define the noncentered measure: do not also add the centered AR1 prior or its Jacobian. For an independent centered-target check, the equivalent log density is `logp_centered(q)+T*log_sigma_h-.5*log(1-rho*rho)`.

Start with one untransformed `pm.Flat('q', shape=D)` and one normalized `pm.Potential`, as in [the local-level workflow](pymc_workflow.py). This makes ordering and automatic transforms explicit. All distribution constants must be explicit float64, including `nu`, `.3`, and prior scales; a float64 configuration alone previously failed to guarantee float64 scalar constants in the local workflow. Named random variables and friendlier output are a later usability layer, after parity is established.

## 2. Linear-cost graph and immutable data first

Implement the recurrence with `pytensor.scan`: scalar previous state, `z_path[1:]` as the sequence, `h[0]` as `outputs_info`, and `mu_h,sigma_h,rho` as explicit non-sequences with `strict=True`. Concatenate the initial state with the scan output. Handle `T=1` without a scan. The graph must contain no random operation or mutable update.

Installed PyTensor source inspection indicates that its Numba `Scan` dispatch generates a compiled loop and that reverse differentiation constructs a reverse scan. This supports an O(T) forward/reverse design; it is **not evidence that this particular graph compiles or has measured O(T) runtime**. Avoid a dense triangular matrix, a length-T Python-unrolled symbolic graph, or inverse powers of rho followed by a cumulative sum. Those alternatives respectively introduce quadratic work, graph growth, or numerical instability.

The initial implementation embeds independent copied arrays as graph constants, or explicitly freezes data using PyMC's `freeze_dims_and_data`. Bind their hashes to the compiled-target record. Do not advertise mutable `pm.Data` support. Inspect the actual compiled graph inputs and reject unsupported additional runtime inputs clearly.

Source-based concern: the current public adapter extracts `fn._pytensor_function.vm.jit_fn` and its C callback invokes `inner(x)`. Ordinary PyTensor Numba thunks can pass all graph inputs, including shared inputs. No explicit binding of additional data arguments is apparent in that adapter. Consequently, its documented snapshot behavior needs an executable test; it cannot be inferred from the presence of a C callback. Changing data requires a new target until a dynamic-data contract has been implemented and verified.

Relevant installed sources inspected: `pytensor/link/numba/dispatch/scan.py`, `pytensor/scan/op.py`, `pytensor/link/numba/dispatch/basic.py`, `pytensor/link/numba/linker.py`, `pytensor/link/basic.py`, `pytensor/link/utils.py`, and `pymc/model/transform/optimization.py`. Adapter source: [owalnuts Python integration](../../integrations/python/python/owalnuts/__init__.py).

## 3. Correctness gates before sampling timings

Implement these checks in a new flow workflow and focused tests without changing the frozen existing experiment artifacts:

1. **Layout and starts:** validate returned dimension and variable ordering. Consume the exact canonical chain matrix from `data.initial_positions` through [flow_starts.py](flow_starts.py), then apply its exact inverse noncentered map. Verify canonical → noncentered → canonical round trips for dispersed nondefault starts, `T=1`, and multiple G. Proposed tolerance: `rtol=1e-12, atol=1e-12` on moderate finite points. Record both matrices; never initialize every latent innovation to zero as a substitute for transforming starts.
2. **Normalized density and gradient:** compare the actual ctypes-callable C target against the independent float64 JAX target and the centered-density-plus-Jacobian identity. Test `(T,G)=(1,1),(8,2),(128,4),(1000,4)` with fixed, recorded nontruth points, supplied starts, and moderate perturbations of every parameter block. Proposed value tolerance: `rtol=1e-10, atol=1e-8`; gradient tolerance: `rtol=1e-9, atol=1e-8`. Record maximum absolute errors and the full point hashes. Add a small finite-difference directional-gradient check independent of both autodiff implementations. A failure stops performance comparisons; do not widen tolerances after seeing results without a new protocol revision.
3. **Compiled execution:** treat Numba object-mode fallback warnings as failures of the no-Python-per-evaluation claim. Inspect the resulting dispatchers/signatures and unsupported-op warnings. A successfully created outer C callback alone is insufficient evidence that its inner graph avoids Python fallback.
4. **Boundary behavior:** exercise finite ordinary points, extreme log scales, and finite-density/nonfinite-gradient proposals. The existing adapter contract maps nonfinite density or gradient to `-inf` and a fully zero gradient so the sampler can reject the proposal recoverably. Verify no NaN crosses the ABI, finite outputs remain unchanged, and invalid initial positions still fail verification. Preserve failures; do not silently substitute gradients.
5. **Outputs:** transform every retained path back to the canonical h coordinates with a stable recurrence outside the sampler. Assert exact requested chain/draw/dimension shape, finite draws, matching seeds/settings, and successful start round trips. Charge output conversion and diagnostics to end-to-end time. JAX parity tooling need not become a production dependency of the Python workflow.

After these gates, run a tiny smoke test for transport and serialization only. Its healthy status, if any, is not reliability or calibration evidence.

## 4. Changed-data safety tests

Before any reuse claim, run deterministic tests on two distinct same-shape datasets A and B whose target densities differ at fixed points:

- Compile A from copied constants; mutate the caller's original arrays. The compiled A target must retain its declared A density and hash. Compile B separately and verify B matches its own trusted density/gradient and differs from A where expected.
- Construct a `pm.Data` version and inspect its compiled graph inputs. Test before and after `set_data`, comparing the actual C callback to trusted PyMC/JAX evaluations. Accept only an explicit supported contract: an immutable snapshot, or correctly bound dynamic data. A clear unsupported-input exception is acceptable for the initial release; silently stale data or an undocumented behavior change is not.
- Repeat with a changed shape. An old dimension or graph must not be silently reused. Require a rebuilt target with the correct new dimension.
- Verify a previously compiled target remains valid and unchanged after another target is compiled, and that its required model/callback buffers remain alive.
- If dynamic data is subsequently implemented, test same-shape A→B→A, independent-target parity, fresh chain starts/seeds, and full adaptation reset for each new posterior. Never reuse adaptation merely because a graph cache was reused.

These are proposed tests, not assertions that the current adapter passes them. Any shared-input defect should receive a narrow integration regression and review before a new frozen timing campaign.

## 5. Timing stages and execution manifest

After correctness checks and source freeze, create an immutable plan containing source and binary/environment hashes, data and start hashes, disjoint dataset/chain/predictive seeds, arm order, CPU mask, timeout, warmup, precision tiers, diagnostic scope, cache policy, and intended cell denominator. The initial exploratory demanding workloads are `(128,4)` and `(1000,4)`. Use four chains, 1000 warmup, and retained tiers `[1000,2000,4000,8000]` unless a new manifest prospectively specifies otherwise. No sampling, build, or competing compilation runs concurrently with a measured cell.

First measure target setup and repeated fused density/gradient calls at recorded nontruth points across the workload sizes. Separate graph construction, compilation, and steady repeated calls where the public API exposes them; otherwise label the combined interval honestly. Record call counts, CPU/wall time, warnings, memory where available, and cache state. Scaling inconsistent with the proposed linear graph prompts profiling before full sampling. This stage cannot establish a sampler speedup.

Then compare the public PyMC flow route with the best validated NumPyro noncentered implementation, preserving the same physical model, data, starts, CPU budget, and endpoint precision gate. The reference must use the optimized recurrence and may continue retained sampling with adaptation frozen when that workflow is supported and verified. The oWALNUTS public route may compile once and fully restart each tier if it has no public continuation API; charge every discarded attempt and warmup. Native Rust may be included as a diagnostic ceiling, clearly labeled as a different authoring workflow.

Health requires zero retained divergences, rank Rhat ≤1.01 and bulk/tail ESS ≥400 for **every canonical coordinate and reported functional**, with sampler errors and depth-limit behavior recorded. For each prespecified reported functional and predictive 90% interval, both endpoint MCSEs must be ≤2% of its width. Nonfinite or zero-width intervals fail. Reuse the existing screen rather than narrowing the scope after results. Predictive simulation includes future state and observation noise and reports its added Monte Carlo uncertainty; fixed supplied future x is a conditional scenario, not an operational forecast from the training cutoff.

Primary cost is invocation to serialized checked intervals, including imports, setup/JIT, all warmup and retained attempts, coordinate conversion, diagnostics, predictions, and output. Report installation/build costs separately, and expose sampling/call costs as secondary decomposition. Balanced sequential order across fresh dataset/seed pairs is required for subsequent comparative evidence. One favorable fixture is exploratory. If either arm fails the frozen precision cap, there is no finite equal-precision speedup ratio for that pair.

## 6. Cold process versus reused compilation

Keep three distinct experiments:

| Track | What can be reused | Required accounting |
| --- | --- | --- |
| Fresh process, existing disk caches | Environment and declared persistent compiler caches | Full invocation; call this process-cold, not compiler-cache-cold |
| Fresh process, isolated empty caches | Installed packages only | Setup plus compilation; use a new isolated cache directory, never delete user caches |
| Long-lived process | Already compiled target for the same immutable data; validated graph/kernel caches for new targets | First compilation plus every refit, reset, diagnostic, conversion and write; separately report first and later fit costs |

PyTensor Numba source includes persistent caching and constant-dependent graph cache keys. Therefore new immutable y/x may require recompilation even at the same shape. Same-data compile reuse and same-shape changed-data reuse are different claims. The first implementation may support only the former. For the changed-data track, create a new immutable target per dataset, record actual compile/cache behavior, and compare with the reference's supported dynamic-data reuse. Do not force the reference to recompile to make policies superficially identical. Any future dynamic C-ABI extension is a separate implementation proposal.

## 7. Negative results and next decisions

Reserve each cell before launch. Store the frozen settings, source/environment/cache/data/start hashes, stdout/stderr, compilation warnings, terminal status, elapsed time, target calls, all tier outcomes, diagnostic failures, raw-draw hash and result paths. Missing cells, timeouts, compiler failures, unsupported scan operations, invalid outputs, and unhealthy or imprecise fits remain in the planned denominator. Never overwrite a failed cell with a successful retry; corrections receive a new artifact path and link to the original failure.

If scan cannot compile without Python fallback, record that limitation before exploring another representation. If compilation succeeds but target cost scales poorly, profile the graph before changing the sampler. If target evaluation is fast but interval precision fails, investigate geometry and adaptation on new exploratory fixtures rather than claiming a transport win solves inference. If both arms reach the same endpoint precision, proceed to a prospectively powered, balanced workload comparison under the qualification requirements. Real-data ingestion, temporal availability checks, out-of-sample predictive usefulness, and market decision value remain separate work even if all synthetic gates pass.
