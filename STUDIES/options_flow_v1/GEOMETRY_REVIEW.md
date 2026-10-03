# Geometry candidates for the long flow model

Read-only review, 2026-10-03. No builds, sampling or timing were performed.
Recommendations below are hypotheses, not qualified improvements. The relevant
comparison is time to the same healthy interval precision against the optimized
NumPyro implementation, including construction/adaptation overhead.

## The geometry we can exploit exactly

The centered layout is `g=(beta_bar,log_tau,mu_h,log_sigma_h,z_alpha,z_beta)`
followed by h[0:T]. Let sigma=exp(log_sigma_h), r=y-location, and
u=r^2*exp(-h)/nu. For one observation the negative log likelihood curvature in
h is exactly

    c = (nu+1)/2 * u/(1+u)^2 >= 0.

Thus, conditional on globals, the path posterior is strictly log concave. Its
negative Hessian is tridiagonal K=Q_AR+diag(sum_g c_tg). For T>=2 the stationary
AR(1) prior precision has first/last diagonal 1/sigma^2, interior diagonal
(1+rho^2)/sigma^2, and off diagonal -rho/sigma^2. For T=1 use
(1-rho^2)/sigma^2. These endpoint formulas follow from the stationary initial
state; substituting the random-walk initial formula is a target mismatch.

For any finite sigma>0 and abs(rho)<1, Q_AR is SPD; adding nonnegative likelihood
curvature preserves SPD. The expected observation curvature under the model is
nu/[2*(nu+3)] per group, which is 5/16 at nu=5. A deterministic Fisher path block
can therefore use c_t=G*5/16 without truth or fitted data. This is a principled
screening baseline, not a claim that actual local curvature is constant.

Noncentering whitens Q_AR at the *current* sigma and mu. Its likelihood Hessian
is then dense in innovation coordinates, and moving log_sigma simultaneously
moves every reconstructed path value. That can improve near-prior geometry yet
leave a slow scale direction on a long observed path. A fixed posterior-based
whitening offers a different tradeoff: observation stiffness is accounted for
without making the coordinate transform itself depend on sampled globals.

## Exact mass convention: do not invert twice

`DiagonalMass`, `DenseMass`, `StructuredCovarianceBlock` and arrowhead operators
all describe **momentum covariance M**, with kinetic energy p' M^-1 p / 2.
For an approximately Gaussian target with position precision H, choose M=H,
not H^-1. In particular `BidiagonalCholesky {diagonal,subdiagonal}` represents
M=L L', so pass the lower-bidiagonal Cholesky of path **precision K**.

Its recurrence is l_0=sqrt(K_00), b_i=K_(i+1,i)/l_i,
l_(i+1)=sqrt(K_(i+1,i+1)-b_i^2). Reject nonfinite/nonpositive pivots; do not
silently replace a failed construction with an unreported metric. A declared
small ridge is allowed but must be recorded. Never use the AR covariance block
merely because the prior has AR covariance; optimal momentum covariance is the
corresponding posterior precision.

The fixed structured wrapper transforms u=L' q and evaluates q=L'^-1 u; its
gradient is L^-1 grad_q. A custom affine version q=q_ref+L'^-1 u also has a
constant Jacobian. Include -logdet(L) when comparing fully normalized transformed
densities; omitting the constant has no effect on sampling. Starts and outputs
must be transformed exactly and checked against canonical starts.

## Candidate 1: fixed path whitening with residual diagonal adaptation

This is the lowest-cost new mechanism to screen.

1. Choose sigma_ref without truth. First screen the prior median exp(-1.5) with
   Fisher curvature above. Then compare a fully costed deterministic reference
   point fitted to training data, or a single discarded pilot estimate with
   a declared budget. Never read fixture truth or held-out y.
2. Form K_ref and its bidiagonal Cholesky L. Use centered physical coordinates
   with h=h_ref+L'^-1 u_path and unchanged global coordinates.
3. Run the existing `Sampler` with `Metric::diagonal()` **on transformed
   coordinates**, allowing global and residual path scales to adapt. Transform
   retained samples back to centered physical coordinates for diagnostics.

This route requires a small study-local target wrapper, not a core driver
change. Each value/gradient costs two O(T) triangular solves; avoid per-call
dense matrices. The direct `Metric::Structured(StructuredBlockMass)` route is
also valid but fixes the global metric as well as the path block, confounding a
poor global scale with the path experiment. Treat it as a separate mechanism
control rather than the only implementation of the candidate.

A data-derived alternative chooses h_ref and globals by a bounded, reproducible
optimizer and uses exact observed c_t. The path conditional mode can be solved
with damped Newton and tridiagonal solves because its conditional objective is
strictly convex. Joint optimization is not globally convex: Student-t location
curvature and hierarchical terms can be indefinite. Use line search and safe
fallbacks; do not call a local Hessian guaranteed SPD in the full space.

The candidate may still lose because sigma changes enough that one frozen K
becomes inaccurate, or because global/path coupling remains. Measure the slow
functionals and interval MCSE instead of inferring success from smaller depths.

## Candidate 2: fixed mean-path shear, then posterior whitening

The prior supplies a known leading coupling: for globals mu_h and path h,
the negative cross Hessian is B_mu=-Q_AR*1. With K_ref=Q_AR+C_ref,
the local conditional response is

    a = K_ref^-1 Q_AR 1,
    h = h_ref + a*(mu_h-mu_ref) + L'^-1 u_path.

This interpolates between prior noncentering in mu (a approximately 1 when
observations are weak) and centering (a small when data dominate). It removes the
leading local mu/path cross curvature at the reference point while keeping the
Jacobian constant. The gradient contribution to mu is a' grad_h; u_path gradient
is L^-1 grad_h. Both models and starts remain exactly equivalent.

More generally, use a frozen matrix A=-K_ref^-1 B for selected cross-Hessian
columns, including log_sigma if stable, and h=h_ref+A*(g-g_ref)+L'^-1 u. Computing
each column requires one O(T) tridiagonal solve. No Hessian position update occurs
during retained sampling. B must be independently checked; a linear shear cannot
remove the entire nonlinear scale funnel. Start with the exact mean column to
isolate the mechanism before adding noisy estimated columns.

A full local metric H=[[Hgg,B'],[B,K]] is SPD only if its Schur complement
S=Hgg-B'K^-1B is SPD. If constructing a full whitening, regularize/factor S
explicitly and report the ridge. Do not pass an arbitrary Hessian cross block
to a factorization and assume the full mass is SPD merely because K is SPD.

## Candidate 3: projected global/path covariance, after generalizing the driver

Existing `LowRankArrowheadMass` supports up to 64 globals and rank 16. Its factor
is L=[[G,0],[P U V',P]] and is SPD by construction for valid positive-diagonal
factors. The constructor's G is a **Cholesky factor**, not a precision matrix.
The path diagonal block of L L' includes the coupling contribution: inserting
P=chol(K) and arbitrary U,V does not preserve an intended path block K.
`new_with_path_subspace` supports the complementary projected factor needed by
the existing adaptation implementation.

Practical blocker: both `sample_projected_arrowhead` and
`sample_chains_projected_arrowhead` in `src/walnutpie/research.rs` currently
require exactly **six leading globals**. The flow target has 4+2G globals,
which is 12 when G=4. It cannot use these drivers as-is. Their internal
`ProjectedCovariance` already tracks a variable global dimension, but all
admission/workspace assumptions and tests must be audited before relaxing the
public guards. Do not remove the guard without that audit, drop six globals,
or pad/reorder sampled parameters to disguise the mismatch.

The collector projects **whitened path coordinates P' h** into an orthonormal
basis, estimates covariance jointly with all globals, regularizes it, inverts to
precision and constructs the arrowhead factor. Therefore choose basis vectors
in that whitened space. For the mean coupling, orthonormalize P' a, not simply
the physical all-ones vector; use a second scale-response column or a few slow
path modes only when supported by diagnosed correlations. A physical level/trend
basis copied from a different study is not automatically meaningful here.

Pooled boundary adaptation can estimate these small projected matrices cheaply
relative to dense T-by-T covariance, but the repository already records early-
window variance underestimation failures. Prefer a one-shot late estimate or
strict sample-count/shrinkage safeguards as the first study; freeze before
retention. Record fallback/conditioning events and every pilot transition.

## Diagnostic order and fair decision

First identify whether log_sigma, mu, group coefficients, path low-frequency
functionals or predictive endpoints decide precision. Record their cross-chain
behavior and relationship to latent roughness, mean and scale. A slow nonlinear
scale direction may defeat a linear metric; this would falsify this candidate,
not justify weakening its health gate.

Screen candidates 1 and 2 on the already identified diagnostic fixtures, then
confirm on fresh seeds if promising. Include exact prior-Fisher versus observed-
curvature construction to identify whether fitting cost is necessary. Expose
the identical affine target to optimized NumPyro, so an advantageous coordinate
system is not credited solely to the oWALNUTS kernel. Keep the native and autodiff
target paths visible to distinguish numerical backend cost from sampling work.

Charge optimizer/pilot calls, matrix construction, coordinate transforms,
warmup, all failed tiers and prediction to full elapsed time. A frozen metric
reused over later fits needs a separate amortized claim and an explicit rule
for when it is rebuilt. No truth-based metric, free pilot, ignored early failed
chains, or healthy-only timing denominator is acceptable.

Required checks before interpreting a candidate: normalized transformed-density
parity, independent gradients, round-trip canonical starts/draws, exact Gaussian
control with momentum covariance convention verified, no change to target
predictions, and fresh-seed time-to-identical-endpoint precision on demanding
paths. Core driver generalization additionally needs arbitrary-global-dimension
tests, sequential/parallel identity and unchanged existing fingerprint/oracle
checks. Generic warmup-statistic retuning is not the proposed mechanism.
