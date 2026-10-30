# Source correction and numerical scope

The archived Stan model's `curve` function uses an analytic Bateman expression
when `linear=1`; only `linear=0` invokes the BDF/RK45 solvers. The previous notes'
claim that the linear population target imposed unnecessary numerical ODE solves
was incorrect. `reference_model.stan` preserves the inspected compiled-model source.
The new C++ target removes twelve per-subject Stan autodiff calls and improves
stability near coincident rates. Preflight timing labels `ode` name the historical
backend, not the algorithm used by its linear branch. No ODE-removal speed claim.

The 462-point derivative/offset audit and six-point prediction parity plus two
extreme-rate limit checks passed. This is a numerical-domain audit, not a proof
of uniform floating-point accuracy over all real parameters. Native callbacks
reject nonfinite evaluations. No sampled mode-mass bound follows from these tests.

The first two importance jobs exited on strict JSON serialization after
zero-weight extreme proposals produced nonfinite summary arithmetic. Their
source, warning logs and supervision files remain immutable. The repaired run
uses the same random seeds/proposals, removes only exactly zero-weight rows from
weighted moments, and evaluates forecasts with log-domain limiting expressions.
Unweighted Laplace rows are not dropped: undefined numerical moments are reported
as null with nonfinite counts, while predictive density includes zero-density
limits. This is a computational repair, not independent statistical confirmation.
