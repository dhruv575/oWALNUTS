# Fresh pilot and fixed-map fitting

One independent pilot per frozen dataset, seed949600001+scenario. Raw native diagonal NUTS at acceptance .999, four chains,1100 warmup and2000 retained, maxdepth10,no jitter. This uses the previously qualified robust diagonal baseline rather than the original exposed-map pilot's low-rank setting. Keep this change explicit; do not attribute its effect solely to the map. Pilot randomness is disjoint from references and subsequent production.

All24 quantities must pass finite/Rhat<=1.01/bulk and tail ESS>=400/zero retained divergences, mean error<=.1 reference SD, relative SD error<=.1 and combined-reference-MCSE z<=4 against the qualified independent reference. Do not train a map from a failed pilot; preserve its result and do not retry or extend it under this protocol. Failure of a dataset remains part of the study.

For each qualified pilot use exactly the first100 retained positions per chain (400 total), unchanged K=4,ridge10 and existing bounded_transport.fit. Save the map and constructed affine/bounded target data. Charge the full pilot, including unused retained draws. Reference values are used only for qualification, never fitting; no TRUTH.json access. Map-fitting errors are failures, not permission to alter settings. Compiled-target equivalence must be checked before production.

Four concurrent workers at most,BLAS1,four chains each,180s/2GiB/64MiB per worker,2GiB free disk. Preserve raw draws, original-coordinate diagnostics, hashes and setup artifacts. No performance, generalization, application or novelty claim follows from map preparation alone.
