# Result: a measured ODE sampling advantage, not a validated application advantage

The corrected 117-job pilot completed with every job returning results, every
process group drained, disjoint phase seeds, unchanged source freezes and
verified training/holdout partitions. All seven retained-reference numerical
audits passed. Original forecast failures remain in the separate legacy archive.

On the public nonlinear ODE benchmark, WALNUTS qualifies 8/8 fresh seeds and
tuned NUTS 7/8. Across the seven jointly qualifying pairs, WALNUTS is **1.65x
faster in native kernel time** (descriptive bootstrap 95% interval 1.58–1.73)
and **1.61x faster in cold worker totals** (1.54–1.68). Both engines share the
same compiled likelihood, gradients, starting points and tuning budget. This
extends the earlier evaluation-cost finding beyond a curved Gaussian example.
The fixture's clinical provenance is unverified; it is a computational result.

The full practical-success rule is **not met**. On this qualified benchmark,
Laplace fails parameter-mean accuracy, particularly log observation noise, but
meets the tested forecast-mean and exceedance-probability tolerances. Its largest
forecast error is only 0.074 times the allowed bound. MAP plus Gaussian draws
take 0.085 seconds; the complete worker takes 5.10 seconds. This does not prove
Laplace reproduces the full predictive distribution or posterior uncertainty.

For observed Theoph subjects 1–3, all 24 WALNUTS validation fits pass diagnostics;
23/24 tuned NUTS fits do. However, none of the nonlinear patient references
passes the frozen reference gate. Subject1 has one retained divergence;
subject2 has two plus a between-run mean-agreement failure; subject3 fails
mean agreement despite zero divergences. R-hat and ESS are otherwise strong.
These conservative qualification failures block matched-accuracy speed claims;
the table's zero accuracy passes mean **not established**, not demonstrated
inaccuracy of every fit. No reference budget was extended after seeing this.

The exact linear-elimination model's three references qualify. Its descriptive
heldout log score exceeds the nonlinear model for two subjects and is slightly
lower for the third. Because the nonlinear references are unqualified and there
are only six heldout observations, this is neither a formal model-selection
result nor clinical validation. It does not establish a need for nonlinearity.

The evidence supports a narrower direction: investigate full-posterior ODE
inference where cheap approximations miss an independently justified uncertainty
requirement. Before another scale-up, freeze decision-relevant functionals,
establish qualified independent references and retain specialized/analytic model
controls. Do not turn the favorable runtime result into a medical, commercial,
AMM profitability or uniqueness claim. Deployment is outside this study.

See [full tables](REPORT.md), [machine-readable results](SUMMARY.json),
[campaign audit](AUDIT.json), [local archive verification](ARCHIVE-VERIFICATION.json)
and [private S3 restore verification](S3-VERIFICATION.json).
