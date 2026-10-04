# Matched target-call result

Both contained processes exited successfully. All 24 blocks and 36,000 target calls are retained; no repeat was performed. Configuration identity remained unchanged throughout both admissions and executions. Total outer time was 17.779 seconds.

Across both processes, median baseline cost was 73.978 microseconds per call and candidate cost was 62.903 microseconds. The median of 12 paired block ratios (baseline/candidate) was 1.1703, ranging from 1.1105 to 1.2002. With baseline compiled first, the median paired ratio was 1.1792; with candidate compiled first, it was 1.1600. These are descriptive dependent loop timings, not a confidence interval or sampler speed claim.

Compilation times varied with order: baseline/candidate 3.043/2.402 seconds in AB, candidate/baseline 2.677/2.479 seconds in BA. Existing compiler caches were retained; no robust compilation advantage is inferred.

Both actually compiled implementations passed the five saved-point value and gradient checks in each process (20 checks total), plus the four deterministic stress comparisons per process. Maximum saved-point value discrepancy was 1.55e-11 and gradient discrepancy 3.41e-13 against the separately JAX-validated archive. CPU0, 8 GiB process memory cap, and a 600-second contained timeout per process were applied. No handwritten derivatives, new random streams, or MCMC were used.

The normalized algebra is a promising target-level optimization: roughly 15% less median call time in this microbenchmark. It does not establish a workflow gain, preserve identical sampler trajectories under floating-point perturbations, or resolve numerical-domain limitations. The earlier boundary evidence includes six mathematically finite regimes rejected by both targets and remains unchanged. No general replacement or deployment follows from this result.

Exact sources are archived in executed-sources.zip with SHA256 mapping. Original plans/configurations, validation and boundary outcomes remain untouched. Exact commands, hardware records, compilation costs, block measurements, and result bindings are saved beside this note.
