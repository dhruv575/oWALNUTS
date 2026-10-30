# Population PK: qualified posterior, no WALNUTS advantage

Completed 2026-10-30. This is useful Bayesian inference work, but it does not
satisfy the continuing goal of a competitive application or substantive sampler
improvement. Deprioritize this candidate as a WALNUTS advantage.

Two independent exchange-augmented PyMC NUTS runs pass the frozen 68-functional
reference screen: worst R-hat 1.00069, minimum bulk ESS 3820, minimum tail ESS
4091, zero retained divergences/depth hits/callback errors. Maximum independent
mean disagreement is 2.078 combined MCSE. The reference includes 43 unconstrained
parameters, 24 withheld-time log predictions and sigma. This is a practical
sampling reference, not a rigorous bound on unvisited secondary-mode mass.

Fresh matched native fits use identical primary-mode starts, whitening, 1000
warmup/4000 retained draws and target acceptance .99:

| Engine | Seconds, two seeds | Minimum bulk ESS/second | Maximum mean error / reference SD |
|---|---|---|---|
| WALNUTS | 14.53, 14.17 | 152.85, 154.84 | 0.0387, 0.0369 |
| NUTS | 9.84, 9.81 | 214.81, 211.21 | 0.0671, 0.0466 |

All four pass the prespecified retained-draw convergence, ESS and mean-accuracy
checks, with zero retained divergences/depth hits. NUTS delivers ~1.38x the median
minimum bulk ESS/second. These two seeds do not establish broad superiority.
WALNUTS recorded 10 and 153 callback errors across entire fits; phase is unresolved,
so they must not be called retained failures or silently discarded. Native NUTS
recorded zero in this fresh comparison. The earlier native reference-screen fit
with one unseparated callback error is conservatively marked unqualified in its
JSON; that flag is not proof of a retained numerical failure.

The raw primary-Hessian Laplace approximation has parameter mean errors up to
3.15 posterior SD and log-forecast mean errors up to 2.40 SD. The tested adaptive
defensive importance baseline fails badly at 262144 final draws after two 32768
draw fitting rounds: ESS 1.71 and 1.0003, Pareto k 4.90 and 4.82. This rejects
these proposals, not all possible importance methods. Its delta-method MCSEs
and mode-mass estimates are unqualified. Failed initial serialization runs and
the numerical repair are preserved; see SOURCE-CORRECTION.md.

Reference posterior prediction improves the mean two-observation subject log
score over raw Laplace by 0.517 and 0.523 across the two approximation seeds;
descriptive paired subject bootstrap intervals are [0.149,0.810] and
[0.154,0.816]. Against MAP the difference is 0.843, interval [-0.551,2.619].
The 24 measurements were already exposed during model selection, so this is
exploratory evidence, not independent predictive validation or a clinical claim.
NUTS can supply the same posterior uncertainty more efficiently here.

A source audit corrected an earlier assumption: the original linear branch
already used the analytic Bateman curve inside Stan, not numerical ODE solving.
The new stable C++ gradient removes per-subject autodiff overhead. It passes
462-point gradient/density checks (max scaled gradient difference 5.96e-11,
offset spread 8.94e-8), finite differences (1.71e-7), prediction parity (1.50e-14)
and extreme-rate limit checks. Small equal-call timing blocks suggest ~2.6x
backend acceleration, benefiting both engines; this is not a sampler improvement.

All six long-reference jobs, four fresh native jobs and two repaired importance
jobs finished within resource caps. Both original failed importance jobs remain.
A 57,267,303-byte archive contains 953 verified members, including source, native
binaries, data/dependencies, draws, diagnostics, failed runs and control packages.
Private S3 exact-version restore and all member hashes passed; receipt is in
qualified_archive. No original evidence was reclaimed. Research goal remains active.

Next: review existing failure/overhead evidence before selecting another sampler
change. In particular, the prior conditional-metric-reconsideration experiment
still fails its frozen median-efficiency gate; the isolated rescued seed is not
permission to claim success under a more favorable post-hoc estimand. A new
candidate needs a concrete mechanism, preserved negative controls, and fresh
prespecified validation against the current automatic selector.
