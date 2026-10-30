# Spatial model runtime qualification

Use only frozen primary training data (712 included trees,200 cells,205 raw
parameters). No heldout likelihood or scores. Compile the frozen model with
BridgeStan2.9.0,STAN_THREADS=true,-j1. At8 normal(0,.25) raw points seed952100001,
require finite density/gradients and405 physical quantities(rho,alpha,beta3,
f200,exp(f)200). Independently construct RBF covariance/Cholesky and linear mean
in NumPy; require maximum f discrepancy<=1e-5 and density-offset spread<=1e-5.
Check five coordinates(0,1,2,5,204) by central differences step1e-4;scaled error
abs(fd-grad)/max(1,abs(grad))<=1e-3. This is a numerical smoke,not inference proof.
One local build/check300s/4GiB/256MiB in new build directory;preserve failures.

On existing AWS runtime,rebuild the verified counting wrapper around this new
library. Eight direct/wrapper gradient probes must agree to1e-10,with exactly8
gradient calls and zero other API calls. Then native diagonal.9 and WAL dense.9,
4chains50warmup30retained,seed952100002;require finite4x30x205 positions and405
physical quantities on retained draws. No convergence or speed qualification.
One AWS BLAS1 job300s/4GiB/128MiB,initial disk>=1GiB. No retries or extensions;
failures preserved for reviewed diagnosis. Freeze references/controls separately.
