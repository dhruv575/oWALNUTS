# AWS-specific pilot qualification after cross-runtime nonidentity

The original AWS full-workflow attempt remains failed. Qualify its saved pilot
samples separately; do not rerun/select seeds. For each of four datasets use the
bounded-WAL workflow's PILOT-RAW.json (seeds950200001..4,4chains1100warmup2000
retained). Compare saved pilot draws and target-call counts with all other three
transformed workflows on that dataset; require exact within-AWS replay.

Recompute all24 physical functionals using the verified compiled original model.
Require finite,Rhat<=1.01,bulk/tail ESS>=400,zero retained divergences,combined
reference MCSE z<=4,mean error<=.1 reference SD,relative SD error<=.1. Same gates
as the local pilots. Fit unchanged K4/ridge10 on first100draws/chain only after
qualification; preserve input hashes,draws,functionals,maps,costs and failures.
This is qualification of saved exposed pilots, not fresh generalization.
Only qualified maps may support a separately frozen study with fresh production
seeds. Original cross-runtime equality requirements/results are not rewritten.
Bound this audit to180s/2GiB/128MiB; one BLAS1 worker. No scientific speed claim.
