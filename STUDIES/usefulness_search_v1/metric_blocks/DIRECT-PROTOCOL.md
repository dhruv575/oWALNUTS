# Direct earnings posterior qualification

Frozen 2026-10-30 before execution. Use exact archived earnings model/data and
qualified reference from model01. Verify full-rank QR design [1,height,male,
height*male], y=log(earn), N>p+1. Flat priors imply alpha=(N-p-1)/2,
b=SSE/2, sigma^2=b/Gamma(alpha,1), beta=beta_hat+sigma R^-1 z.

Preflight 64 independently generated states, seed 928500000. Compare Stan
unconstrained log density differences with -(N-1)log(sigma) minus quadratic
residual/(2 sigma^2); compare all analytic gradients including log-sigma.
Require maximum absolute centered log-density discrepancy <=1e-6 and maximum
gradient discrepancy/(1+abs(Stan gradient)) <=1e-7. No production before pass.
This verifies target algebra and Jacobian, not just empirical moments.

Four fresh independent replicates seeds 928500001--928500004, each four batches
of 8192 IID draws. Batches play the chain role for diagnostic comparability.
Require all coordinates rank Rhat<=1.01, bulk/tail ESS>=400, mean differences
<=4.5 combined MCSE and <=.1 reference SD, SD relative error<=.1. Separately
compare with exact beta/sigma means and SDs, mean error<=.05 exact SD and SD
relative error<=.05. Preserve every result, raw draws, reference, source/data,
failure and timing. No retries or threshold changes. Record fitting, generation
and diagnostic timing separately; imports/process startup excluded from compute
timings. Record 64 verification target evaluations and zero sampling target calls.

Bound entire worker at 180 seconds, sampled RSS 2GiB/output64MiB. Work on dedicated
tmpfs; archive and exact-version restore verify before redundancy reclamation.
Passing would disqualify earnings as an application needing expensive sampling,
but would not by itself decide the general metric-adaptation research question.
