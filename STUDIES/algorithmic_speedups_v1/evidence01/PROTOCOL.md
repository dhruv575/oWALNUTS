# Four algorithmic speedup pilots — frozen 2026-11-01

Objective: investigate routes to >=4x less time to the same verified answer,
with 10x as a stretch target. This is an exploratory engineering/inference
study, not a claim of a WALNUTS advantage or a predictive win.

1. **Grid algebra:** exact 20x10 squared-exponential covariance structure,
   including the existing 1e-10 diagonal jitter. Use a symmetric covariance
   square root and analytic derivatives of the square root via the Sylvester
   equation. Compare dense and grid implementations, finite differences and
   existing Stan physical quantities. This changes whitening coordinates,
   not the physical posterior. Gate: covariance max error <=1e-10, density
   error <=1e-5, normalized gradient error <=1e-3 on fixed probes. Record
   numerical failures without clipping eigenvalues or deleting jitter.
2. **Blocked spatial inference:** Gaussian-prior elliptical slice updates of
   latent field and standardized coefficients; random-walk Metropolis updates
   of log rho/log alpha. Adapt proposal scale only during warmup and freeze it
   for retained draws. Compare one and four field updates per global update;
   compare dense/grid algebra. Four chains, 1000 warmup + 2000 retained for
   initial pilots, two seeds 954100001/954100002. Count eigendecompositions,
   likelihood calls and shrink steps. A bracket iteration cap fails the job
   and preserves its log; an unaccepted candidate is never retained.
3. **Corrected physics proposals:** compare independent Student-t Metropolis,
   two-stage delayed acceptance with a cheap quadratic surrogate, and native
   NUTS/WAL controls on the existing large-angle case. Full-model correction
   is mandatory; the surrogate never replaces the final target. Use the same
   nonlinear RK4 model, value-only evaluation where gradients are unnecessary.
4. **Frozen nonlinear transport:** learn a triangular conditional polynomial
   map using a separate importance pilot, include its Jacobian and analytic
   derivatives, freeze it before retained sampling. Compare against raw and
   affine coordinates with the same sampler and tuning. Charge preparation,
   pilot fitting and diagnostics to full cost. Physics seeds 954200001/2;
   training seed 954200000. Maximum 4096 pilot proposals.

All proposals retain support of the original target. No heldout spatial data
will be opened or used for selection. Physical summaries, R-hat, bulk/tail ESS,
MCSE, forecast functionals and reference discrepancies are distinct gates.
Initial pilot screen: R-hat <=1.01, minimum bulk/tail ESS >=400, no divergences
where applicable. A speed winner also needs agreement with a qualified
independent reference, not just a passing convergence diagnostic. The prior
spatial combined reference is unqualified; comparisons to it are provisional.
Do not weaken existing final reference requirements (ESS >=1000).

Use existing AWS only. One BLAS thread per Python worker, <=12 simultaneous
CPU workers (native four-chain baselines count as four), <=2GiB per worker,
<=900s per job, total new output <=200MiB, stop launching below 1GiB disk free.
Retain failed/timeout outputs, source hashes, seeds, resource observations,
raw draws and method-specific setup/fit/diagnostic timing. Source changes after
a failed preflight require a separately labeled repair and preserved failure.

Primary references:
- https://proceedings.mlr.press/v9/murray10a.html
- https://proceedings.mlr.press/v37/flaxman15 (its Laplace approximation is not
  adopted here; we investigate the grid algebra with the full Poisson target)
- https://arxiv.org/abs/2009.03699
- https://arxiv.org/abs/1412.5492
