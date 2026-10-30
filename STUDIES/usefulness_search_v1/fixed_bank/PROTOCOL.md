# Fixed-bank correctness and oracle diagnostic

Frozen before execution, 2026-10-30. No application/novelty/default claim.
The predecessor live-ensemble screen failed; see ../ensemble_moves/REPORT.md.
For a fixed bank g, accepted forward flux is min(pi(x)g(y),pi(y)g(x)). Thus
the independence transition preserves pi; composing it with fixed local kernels
does too. Bank parameters must not be updated from retained production draws.

Gate 1: seed 942000000, SciPy Student-mixture density parity and accepted-flux
checks in dimensions 1,3,12, 100 random cases each; errors <=1e-10. Validate
bad inputs, no caller mutation, nonfinite proposal rejection. Exact-start
stationarity on 12000 independent four-walker replicates of the unequal-width
mixture below: first/second moments, positive mass and centered cross-walker
product; all absolute z <=4.5, standard errors across replicates.

Gate 2 (only after gate 1 passes): oracle centers (-8,8) on coordinate zero,
zeros elsewhere, identity proposal factors, equal bank weights, Student df5.
These supplied centers bypass discovery. Target coordinate zero is
0.8*N(-8,2^2)+0.2*N(8,0.2^2); others iid standard normal. Dimensions 1,8.
All production walkers start at -8 with other coordinates zero. 16 independent
replicates per dimension/arm, seeds 942100001..942100016, paired across arms.
Arms: local WALNUTS, WALNUTS+bank, bank-only MH, self-normalized importance
sampling (IS) from exactly the same bank. Four walkers for transition arms.
Local tuning: identity momentum mass, step .1, depth10, max error1, no adaptation.
100 chunks of 10 local transitions; augmented arm applies one bank sweep each
chunk. Bank-only applies one sweep per chunk. Drop first20 chunks for transition
arms, then use ensemble-average functionals over80 chunks. IS uses800 proposals
and all weights. Local seed base+1000*chunk; bank seed base+1000000.

Compare mean, second moment, positive mass, and d8 other-coordinate first/second
moments against analytic truth. Across-replicate RMSE/SE, never walker MCSE.
Mechanism gate: augmented positive-mass RMSE <=.05 and mean within3 replicate
SE of truth in both dimensions; no callback failures. Report all other errors.
Independence MH and IS are required cheap controls: a synthetic gate pass alone
cannot credit WALNUTS if these solve the same problem more cheaply. Report every
target evaluation and actual time; no Python-versus-native timing inference.
All oracle assistance must remain explicit; no actual-use-case claim.

128 jobs, deterministic shuffle942000001, max8 workers; each600s/2GiB RSS/32MiB
output sampled caps. Validation180s/2GiB. Root>=1GiB,tmpfs>=2GiB,RAM>=18GiB.
Hash inputs before/after; preserve raw draws, IS weights, failures and monitors.
