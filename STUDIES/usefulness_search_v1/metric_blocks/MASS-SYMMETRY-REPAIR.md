# Explicit mass symmetry repair, frozen before repaired sampling

The first three earnings candidate configurations were rejected before sampling
with "dense mass must be symmetric". Preserve the entire original screen and
do not replace its failure classification. Inverting the ill-conditioned SPD
selector covariance with NumPy introduces small antisymmetric roundoff. The
Gaussian preflight did not expose this installation issue.

Separate repair experiment: use the original frozen starts, pilot, selected
covariance, arm, seeds, iteration counts and reference gates. For every dense
candidate input compute M=(M+M.T)/2 before installation. Require finite SPD and
||C M-I||_F <=1e-7, and relative asymmetry <=1e-10 before repair. Preserve the
original inverse, repaired inverse and all checks. Abort that candidate if any
check fails. No other selector or sampling changes; rerun all candidate cells,
not just favorable failures. Diagonal inputs unchanged. Reuse original completed
controls with explicit provenance; they are not independent new replicates.

The original batch must be terminal before repair starts. Every repair job has
the same 180s/2GiB/64MiB sampled caps and durable raw evidence. Charge the original
pilot and probes to the staged algorithm. Separately report repair CPU/time;
discarded failed launches are development overhead, not silently erased. Repaired
results remain a development screen requiring independent future validation.
