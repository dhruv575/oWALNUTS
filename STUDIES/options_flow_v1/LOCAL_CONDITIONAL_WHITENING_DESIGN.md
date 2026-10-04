# Conditional Gaussian guide for the exact local Student-t target

This is an exploratory derivation prompted by a new residual-coordinate
failure. It does not change the active cohort, choose a successful subset, or
establish a replacement recipe. All guide quantities use observations, declared
prior constants, time increments and the current sampled scales; no generating
truth or auxiliary sampling enters the transformation.

## Exact transformation

Let `a` be the exogenous anchor, `s0=1.5`, `o=exp(log_sigma_obs)` and
`r=exp(log_sigma_rw)`. The original model has `h0 ~ N(a,s0)` and increments
`h_t-h_(t-1) ~ N(0,r*sqrt(dt_t))`, with independent
`y_t ~ StudentT(5,h_t,o)`. Log scales retain their original normal priors.

Use a Gaussian observation guide `y_t | h_t ~ N(h_t,o)`. This specific guide
scale is a prospective choice, not a claim that it matches Student-t variance.
Set `lambda0=1/s0^2`, `w=1/o^2`, and `v_t=1/(r^2*dt_t)` for `t=1..T-1`.
The guide conditional precision `Q=R+wI` is tridiagonal. For T>1:

* `Q00=lambda0+v1+w`;
* `Qtt=v_t+v_(t+1)+w` for interior t;
* `Qlast,last=v_(T-1)+w`;
* `Q_(t,t-1)=Q_(t-1,t)=-v_t`.

For T=1, `Q00=lambda0+w`. The information vector is
`b_t=w*y_t + 1[t=0]*lambda0*a`; the guide mean solves `Qm=b`.
Write `Q=L L^T` with lower bidiagonal L. Define sampling coordinates
`u=(z,log_sigma_obs,log_sigma_rw)` through

`h = m + L^(-T) z`.

The complete joint transform is triangular because the two log scales are
unchanged. Even though h depends on both scales, its full Jacobian determinant
is `det(L)^(-1)`. The exact transformed log density is therefore

`original_normalized_StudentT_joint(h,log_scales) - sum(log(Ldiag))`.

This is an exact coordinate change, not a Gaussian approximation to the sampled
posterior. The inverse is `z=L^T(h-m)` using each position's own scales. Return
canonical h and log scales before evaluating any existing diagnostics,
functionals or predictions. Historical observed-data starts are transformed
exactly; neither starts nor target priors are redefined.

## O(T) algorithms

Given diagonal d and lower off-diagonal e of Q:

1. `ell0=sqrt(d0)`; for t>=1 set `sub_t=e_t/ell_(t-1)` and
   `ell_t=sqrt(d_t-sub_t^2)`.
2. Solve `Lv=b`: `v0=b0/ell0`, `v_t=(b_t-sub_t*v_(t-1))/ell_t`.
3. Solve `L^T m=v`: backward `m_last=v_last/ell_last`,
   `m_t=(v_t-sub_(t+1)*m_(t+1))/ell_t`.
4. Solve `L^T delta=z` by the same backward recurrence and set h=m+delta.
5. Inverse: `z_t=ell_t*(h_t-m_t)+sub_(t+1)*(h_(t+1)-m_(t+1))`,
   omitting the second term for the last coordinate.

There are O(T) arithmetic and storage costs, and no dense matrix is necessary.
Guide factor/mean computations are shared across density and Jacobian within a
single evaluation, but must be recomputed when either sampled scale changes.
Gradients must differentiate the factor, both mean solves, noise solve, original
density and determinant. Freezing Q or omitting mean derivatives is incorrect.

## Gaussian analytic control

Replace the original Student-t likelihood with the same Gaussian observation
guide only in a correctness test. Conditional on the scales, z must then be
exactly iid N(0,1), with no z/scale cross derivative. Let R be the original
latent precision. Its determinant is `lambda0*product(v_t)`. Define

`E(m)=lambda0*(m0-a)^2 + sum(v_t*(m_t-m_(t-1))^2) + w*sum((y_t-m_t)^2)`.

The normalized Gaussian marginal log density of y given scales is

`-T/2*log(2*pi) + 1/2*(logdet(R)+T*log(w)-logdet(Q)) - E(m)/2`.

The exact transformed Gaussian joint is this marginal, plus the original two
log-scale priors, plus `sum(log Normal(z_t;0,1))`. This control catches missing
normalizers, determinant signs, boundary precision terms and omitted scale
derivatives. Using E(m) avoids cancellation in the equivalent `c-b^T*m` form.
It is not a proof that the Student-t posterior becomes independent: heavy-tail
outliers and scale identification can still generate difficult dependence.

## Stability and autodiff implementation choices

The precision is positive definite for every finite positive scale. Arithmetic
can still fail for extreme log scales. Direct inverse variances may overflow,
and `d_t-sub_t^2` can lose precision when process precision dominates weak
observation precision. Do not silently add jitter or clip sampled scales: both
can change the transformation or its derivatives unless fully represented in
the exact density/Jacobian. A factorization failure should be explicit during
evaluation, with invalid transformed points rejected consistently.

First correctness implementation: a PyTensor `scan` for factorization and
forward solve, then a reverse scan for both backward solves. It makes the
recurrences explicit and automatically differentiable, with O(T) graph size at
runtime. However, compiled Scan lowering, reverse-mode storage and loop overhead
need inspection in the actual PyTensor/Numba public adapter; no speed claim is
made. Combine recurrences where it reduces scans without obscuring derivatives.

Existing block-prefix integration is well suited to affine recurrences with
coefficients already known, hence can accelerate the triangular solves after
factorization. Cholesky coefficients themselves follow a nonlinear Riccati
recurrence; reusing a cumulative-sum trick verbatim is invalid. Associative
2x2 transfer formulations are possible but products may be badly conditioned
and require a separately justified normalization/derivative scheme. Start with
Scan parity and a target-call profile before inventing another primitive or
trading numerical stability for parallel prefix speed.

A square-root information/Kalman smoother formulation is another O(T) route
if subtractive Cholesky becomes unstable. Any alternative must yield the same
mean, factor orientation and normalized determinant, not merely an equivalent
approximate covariance. A scale-normalized Q can reduce overflow; its scaling
factor must remain in the solve and log determinant and be differentiated.

## Prospective verification before sampling

For T=1, short irregular-dt series, and larger paths, compare the O(T) factor
and solves with an independent float64 dense reference at declared scale grids.
Check `L L^T=Q`, `Qm=b`, batched canonical round trips and the inverse-Jacobian
determinant. Include process-dominant and observation-dominant regimes, nonzero
anchors, offset observations and invalid/overflow scales.

At fixed nontruth positions, compare PyTensor generated value/gradient with an
independent JAX implementation and directional finite differences of the exact
Student-t transformed joint. Use both absolute and scaled tolerances. Test
log-scale derivatives specifically; agreement only in z directions is weak.
For the Gaussian control require `grad_z=-z`, mixed z/scale Hessian zero, and
value/scale gradients matching the independent normalized marginal above.

Then profile target calls at fixed archived positions, charging compilation
separately; inspect Scan lowering before any expensive sampler comparison.
Only a new source-frozen, prospectively declared paired experiment can decide
whether the extra target cost is offset by improved mixing. Keep all current
cohort failures and do not call their posterior estimates reference truth.
