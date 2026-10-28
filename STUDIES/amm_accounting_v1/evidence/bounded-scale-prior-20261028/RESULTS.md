# Bounded-scale prior sensitivity audit

Deterministic quadrature checked normalization and first/second sigma moments
against the analytic truncated-lognormal formula for caps .5,1,2. All nine
checks agreed within 2.23e-16. Exact source SHA256 was verified after retrieval.

| Cap | Original prior mass excluded | Prior probability volatility differs by >10x from exp(mu/2) |
|---|---:|---:|
| .5 | 3.34324% | .00785555% |
| 1 | .0643471% | .0836293% |
| 2 | .000206064% | .0969877% |

The excursion integrates the stationary Gaussian deviation h-mu over the
truncated sigma prior at rho=.95; it counts volatility above 10 times its
conditional median or below one tenth. It is not the probability of a
10-fold price move or an empirical risk estimate. Conditional on sigma being
at the cap, the central 95% stationary volatility factors are approximately
4.80,23.07,532.14 respectively (reciprocal lower bounds).

Small removed prior mass does not establish a harmless model change, especially
when the removed tail is responsible for divergent posterior/moment integrals.
No cap is selected here. This audit supplies interpretable prior consequences
for a predeclared sensitivity study; scientific plausibility, predictive
calibration and shock behavior still require evidence. The analytic
integrability argument separately requires mathematical review.
