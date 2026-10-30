# Exposed fallback scale repair, not independent validation

Freeze before sampling: rerun only the three already exposed regression fallback
cells929300005,929300008,929300009. Keep stable blocks and reconstruction formula;
replace pilot marginal variances with the diagonal of the existing fitted Fisher
covariance. This also supplies scales to unselected coordinates. No target names
enter the reconstruction; this focused experiment tests a diagnosed mechanism.
Use saved pilot end states, same seed+100000,750 warmup,2000 draws. Compare with
the existing hybrid/v4/Fisher controls; these controls are reused, not replicated.
Charge original pilot,400 scores,64d probes, and new sampling calls. Retain all
original accuracy/reference gates. Require all three repaired cells pass and each
ESS/total-call ratio vs qualified Fisher>=.90 for a mechanism-continuation check.
No claim that this establishes general improvement, useful application or novelty.
Fresh larger validation must follow any successful exposed repair.

Each sampler job bounded180s/2GiB/64MiB with its entire job folder monitored.
Record fit hashes, corrected matrices, supervision and outcomes; retain failure.
No end-to-end timing claim. Do not modify previous failed gate or its sources.
