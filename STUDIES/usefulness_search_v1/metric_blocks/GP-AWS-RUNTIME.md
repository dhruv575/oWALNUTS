# Portable AWS GP runtime

The existing research instance passed raw and bounded compiled-model smoke tests
for both WALNUTS and native NUTS. Exact model and runner binaries were copied;
location-specific counting wrappers were rebuilt. A single gradient probe
counted exactly one gradient call and matched direct model value/gradient.
Four chains x20 retained after30 warmup yielded finite draws in each smoke.
These tiny runs do not establish posterior qualification or comparative timing.

Bundle SHA256 0de87d07eaa5d1109471c141b78ae1c21373cc12789580b665de5e7ead230b1c.
Remote root /home/ubuntu/lanes/gp-portable-runtime-20261030. LD_LIBRARY_PATH
points to its models directory with the exact retained libtbb dependency.
AWS environment now uses nutpie0.16.11, matching the local sampler version;
Python/NumPy versions differ and are recorded in preflight/SUMMARY.json.
No inference result from the prior nutpie0.16.8 environment is relabeled.

The local gp_walmap_comparison01 remains the authoritative current sampler
validation; do not restart or duplicate it. Next full-workflow testing should
include pilot regeneration and map fit as well as the repaired conditional
importance grid, use serial measurements on this one AWS machine, retain all
four datasets and fresh seeds, and measure accuracy jointly with complete costs.
Runtime alone remains insufficient for application value or uniqueness.
