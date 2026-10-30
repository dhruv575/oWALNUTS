# Momentum-sum allocation reuse result

Fresh timing screen passed: False.

The component audit attributes 65.47% of direct-diagonal allocation requests to untraced subtree construction; the 192-byte requests match the leaf momentum-sum vector. An isolated candidate reuses consumed later-subtree vectors in a thread-local pool capped at64 entries and1MiB. It preserves the public Vec field, summation order, selection, RNG and target evaluations. Production is unchanged.

Library qualification:155 passed, one existing ignored. The initial isolated library build lacked repository fixtures and serde_json dev dependency; these were copied/restored and the failed build preserved. Both uninstrumented and allocation-probed candidates exactly reproduce five cold qualification cases (all prior chain fields except elapsed time).

| Case | Allocation requests before | After | Reduction |
|---|---:|---:|---:|
| banana_direct / identity | 8,071,366 | 534,699 | 93.4% |
| banana_direct / diagonal | 3,250,019 | 474,799 | 85.4% |
| banana_latent / identity | 474,493 | 333,287 | 29.8% |
| banana_latent / diagonal | 482,421 | 337,124 | 30.1% |
| funnel / diagonal | 927,510 | 401,198 | 56.7% |

Gross requested bytes and counts are not live memory or runtime. The first timing attempt used a polling timed wait and is invalid for primary timing. Attempt02 repeats every seed set using blocking process wait inside the bounded supervisor. No candidate changes or pair exclusions.

Twenty independent fresh four-chain seed sets per target,1000 warmup/4000 retained draws, random arm/pair order. All60 pairs reproduce every recorded chain field except seconds exactly. Below are geometric mean pristine/candidate runtime ratios and paired95% bootstrap intervals; above1 favors the candidate.

| Target | Process runtime ratio | Sampler-only ratio |
|---|---|---|
| banana_direct | 0.9847 [0.9805, 0.9891] | 0.9843 [0.9799, 0.9889] |
| banana_latent | 0.9868 [0.9697, 1.0063] | 0.9764 [0.9602, 0.9928] |
| funnel | 0.9767 [0.9680, 0.9847] | 0.9741 [0.9649, 0.9822] |

The frozen gate requires primary direct-target lower bound above1.05 and both control lower bounds above.95. Do not promote this candidate if that gate fails. Allocation-count savings alone do not establish useful improvement. These targets also cannot establish superiority to native NUTS, real application value, profitability or novelty. The funnel remains a parity/performance stress case, not a qualified posterior result.

Research direction: close this particular pooling implementation if the timing gate fails. The evidence does not exclude other allocation strategies, but it does remove the basis for treating allocation counts as the main practical opportunity. Prior work already rules out merely deleting reverse checks or retuning permissive energy thresholds. The next useful question is a change in statistical efficiency on a problem with unavoidable varying curvature, with equal-budget native and reparameterized controls; first audit the existing experiment inventory to avoid rerunning rejected settings. The research goal remains active.

Evidence: local_recovery/momentum_pool_test02, momentum_pool_timing02, allocation_attribution01; failed attempts retained. Archive receipt is local_recovery/momentum_pool_archive01/VERIFICATION.json.
