# End-to-end fixed-matrix seam: correct on Gaussian preflight, no advantage

2026-10-30. Isolated harness, unchanged production library. The selector estimates
covariance C; the existing API requires momentum mass M=C^-1. The two-stage
prototype discards a 350-iteration diagonal pilot, estimates curvature from 16
pilot states, installs the inverse selected covariance, adapts step size for 750
more iterations, and retains 2000 draws per chain. It restarts random streams at
the boundary; it is not the existing automatic handoff. All pilot work and 192
gradient probes per candidate are charged. Starts, seeds and gates were frozen.

All 32 jobs (8 pilot, 8 candidate, 16 controls) exited successfully and drained.
All eight candidate replicates pass the known-target gates. Maximum rank Rhat
1.00173, minimum bulk/tail ESS 5185/5486, maximum coordinate mean error .0287
target SD, SD error 2.11%, whitened second-moment spectral error .0487. The
selector finds [0,1] in every correlated case and no block in independent cases.
All sixteen control replicates also pass. These checks support correctness on
these Gaussians only, not arbitrary-target stationarity or nonlinear performance.

On the correlated target, candidate total calls are 68,259--80,921, versus
247,918--258,299 diagonal and 64,854--67,282 full dense. Thus full dense uses
fewer calls in every replicate. A gain over diagonal alone is not an advantage
against the stronger control. Wall measurements cover sampler calls and probes,
not process startup, imports, serialization or orchestration; tiny timings are
not appropriate end-to-end performance evidence. No efficacy claim follows.

Next: extend this same staged harness to actual model targets and the existing
automatic selector, with fresh seeds and reference-qualified functional checks.
The remaining proposed mechanism is stable conditional curvature under changing
scale, absent in these constant-Hessian controls. Freeze that model screen before
running it. Any integrated single-run policy would still need separate timing,
adaptation, fallback, budget accounting and correctness checks. The paper's
usefulness and novelty requirements remain open; no sampler defaults changed.

Inputs unchanged; build completed in 19.55s with sampled peak RSS ~905 MB.
All job raw inputs/draws, source fixture, executable, environment, monitor and
selection matrices are in the private 190-member archive (6,722,570 bytes),
SHA256 eab72b3f8f4e830aa5705a1056684d60fa95d2a6f03ffdadc9d2b45cc1b5d354.
Exact-version restore and member hashes passed; see online_archive receipts.
Remote durable copies retained. Caps are sampled; build output cap excludes
Cargo artifacts, which remain on the bounded dedicated tmpfs.
