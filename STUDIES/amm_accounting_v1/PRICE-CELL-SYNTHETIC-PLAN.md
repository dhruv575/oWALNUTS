# Fixed one-observation posterior check

Scope: a synthetic implementation/fidelity check, not market-model validation,
not SBC, not evidence of an advantage for WALNUTS or any economic objective.

Use T=1, initial log price zero, cell [-0.0005,0.0005), rho=.95, and exactly
the priors in `price_cell_sv.py`. This deliberately permits straightforward
independent prior rejection sampling. Draw mu,log_sigma,beta,z independently
from their priors; draw a Student-t increment conditional on them; retain the
whole joint draw precisely when the increment lies in the cell. The accepted
draws have the augmented posterior law, without MCMC or posterior-density
evaluation. Transform the accepted price to u using the inverse cell logistic.
This oracle is specific to T=1 and cannot validate long-window mixing.

Rejection reference: exactly 1,000,000 proposals, batches of 10,000, seed
398123781. Preserve all accepted draws and the count of nonfinite generated
values. Fail admission on any nonfinite value or fewer than 10,000 accepted
draws. Do not silently discard overflow and claim an exact reference.

Compiled NUTS: four chains, four cores, 2,000 warmup and 4,000 retained draws
per chain, seed 398123782, model initialization seed 398123783, initial center
[2*log(.005),log(.2),0,0,0]. Retain warmup and all sampling diagnostics. Use
target_accept=.9, maxdepth=10, no low-rank metric and no transform adaptation.

Before launch, bind source hashes and pinned runtime; audit these seed values
against the active experiment seed registry. A source-only grep is insufficient
to establish independence from archived seeds. Bound total runtime to 600 s,
process-tree RSS to 8 GiB and output to 256 MiB. Preserve terminal status,
failure records and traces, including on any diagnostic failure.

Report every coordinate's rank Rhat, bulk/tail ESS, mean and mean MCSE; gates
are Rhat<=1.01, bulk/tail ESS>=400, zero divergences. Compare posterior means
to rejection estimates using combined MCMC and independent-reference standard
errors. Report all five discrepancies; abs(z)>4 flags disagreement for review,
not a proof of a bug. Also compare 10/50/90 percentiles descriptively. No
discarding failed coordinates, seed replacement or tuning extension within this
protocol. Passing finite checks is evidence for this single fixture only.

Status: design fixed; execution not yet admitted. Source binding, complete seed
audit and monitored runner remain to be implemented before launch.
