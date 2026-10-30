# 79-observation GP runtime preflight

Use only frozen GP-TRAIN.json (79 observed training years,81 parameters).
Existing verified GP model and sampler binaries; no heldout data on AWS.
Eight seed951100001 normal(0,.25) parameter points: finite density/gradient,
counting-wrapper/direct agreement1e-10,exactly8 gradient calls and zero other
counted calls. Finite160 functionals (rho,alpha,f79,intensity79).
Then native diagonal/.9 and WAL dense/.9,4chains50warmup30retained,seed951100002.
Require finite(4,30,81) draws and successful process drain. Tiny smoke does not
qualify inference, select settings or estimate speed. Preserve failures.
One BLAS1 job300s/3GiB/128MiB; free disk>=1GiB. No scoring or posterior claim.
