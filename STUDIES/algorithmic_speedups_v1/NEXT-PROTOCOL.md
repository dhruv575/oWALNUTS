# Reviewed continuation queue

After the completed pilot checkpoint, run a fresh native-grid confirmation
seed 954100005, four chains, 1000 warmup, 4000 retained and unchanged settings.
Retain full draws within a 28MiB output cap. This is a fresh seed, not a
replacement for any failure. Later audit physical agreement against the
completed controls with unchanged thresholds.

In parallel, measure native-grid versus compiled-Stan kernel scaling on
synthetic regular grids 20x10, 40x20 and 80x40. Generate data with fixed
954300000+N seeds, retain exact data, use identical rho=.7, alpha=1.2 and zero
latent probes (same physical field), check density against both Python grid
and Stan, and native gradients against Python. Five alternating timing batches;
100 native evaluations and three Stan evaluations per batch. These are kernel
scaling measurements, not sampling or predictive-quality claims.

Total reserved CPU slots: five. Each job: 900 seconds, 2GiB RSS. Scaling output
cap 2MiB. Check total lane bytes plus both output reservations stays below
200MiB and disk free exceeds 1GiB before launching. Preserve partial scaling
results if a larger grid hits a resource or numerical limit. No new resources,
data cleanup, heldout access, deployment or trading.
