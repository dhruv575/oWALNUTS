# Independent high-precision derivative verification

The original preflight failed the1e-4-step double finite-difference criterion.
An unchanged-point diagnostic sweep showed maximum scaled errors.00906 at1e-2,
.0000912 at1e-3,.001693 at1e-4,.01120 at1e-5,and.07291 at1e-6. This nonmonotonic
pattern motivates independent high-precision verification; it does not prove
that the compiled gradient is correct. Preserve the original failed preflight.
The diagnostic used120s timeout/BLAS1,without separate RSS/output monitoring.

Use all8 original seeded points,unchanged model including jitter1e-10. Implement
the full log density independently with mpmath RBF covariance,Cholesky,linear
mean,Poisson likelihood and raw-coordinate priors/Jacobians. For rho and alpha
coordinates calculate central derivatives at60decimal digits/step1e-5 and
80digits/step5e-6. Require both estimates to agree within1e-5 scaled by max(1,
absolute fine derivative); require compiled AD agreement with fine estimate
within the original1e-3 scaled tolerance. No selecting a favorable step/point.
At80digits,also compare base-point f to compiled f<=1e-5 and log-density offset
to expected proportional density<=1e-5. Save high-precision strings and errors.
If any check fails,no sampler smoke proceeds under this model.

Eight concurrent AWS jobs,one point each,BLAS1,each300s/1GiB/8MiB. Initial free
disk>=1GiB. No automatic retries/extensions. Target and source hashes frozen.
This reviewed alternative verifies the intended derivative against a separate
implementation; it does not rewrite the earlier failed finite-difference result,
change the statistical model,or establish posterior fidelity.
