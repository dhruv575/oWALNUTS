# Conditional Laplace importance baseline

Frozen after the global-Laplace audit failed, before this baseline runs.
This is a stronger alternative, not a rerun of the failed global approximation.
Laplace marginalization for non-Gaussian GP models is established; see
Rasmussen/Williams section3.4.4: https://gaussianprocess.org/gpml/chapters/RW3.pdf.
The following proposal/importance correction is our explicitly specified
implementation, not a claim to implement the full INLA or GPML software.

For h=(log rho,log alpha), z=f_tilde, L=chol(K), maximize
F(z)=k' Lz-sum(exp(Lz))-.5*z'z by damped Newton from z=0.
H=I+L' diag(exp(Lz)) L is positive definite. Stop max|gradient|<1e-7,
at most100 iterations with at most40 backtracks. Failed solve is a job failure.
Approximate log marginal for h: log prior(h)+F(mode)-.5logdet(H), up to a
common constant. Build41x41 equal-width log-space cells over rho[.5,20],
alpha[.1,10], using midpoint scores. No reference draws inform the proposal.

Hyperproposal is95% piecewise-uniform normalized grid and5% exact independent
hyperprior (Gamma25,rate4 and half-Normal2), both in log coordinates. This has
full support. Conditional z proposal:90%N(mode,H^-1),10%t5(mode,2.25*H^-1).
Compute FULL normalized mixture densities at both levels. Weight exact Stan
target divided by this joint proposal; all priors/Jacobians included consistently.
Save uncorrected proposal summaries too, but do not call the defensive mixture
itself a pure conditional-Laplace approximation.

Preflight seed944000001: numerical target values match Stan up to one constant
at40 points (offset spread<1e-6); conditional gradient agrees with Stan latent
gradient at modes (<1e-5); conditional mixture densities match SciPy (<1e-8),
hyperproposal grid part integrates to .95 and prior part .05 by construction.
Record every conditional objective evaluation, iteration and setup time.

Four fresh independent importance seeds944100001..944100004,16384 draws each.
Reuse the qualified24-functional reference, same accuracy/weight gates as the
original protocol. Require all four. Across-seed errors retained; no posterior
tuning. All numerical failures remain failures, not excluded draws. Charge grid
construction plus every per-proposal conditional solve and exact target call.
No WALNUTS efficiency or actual application claim from this synthetic audit.
Preparation180s, workers600s each,2GiB sampled RSS/64MiB output, four workers.
