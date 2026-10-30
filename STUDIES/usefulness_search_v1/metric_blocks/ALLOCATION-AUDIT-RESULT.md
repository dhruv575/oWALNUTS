# Allocation audit: retained-path attribution warranted

2026-10-30. All ten disabled/enabled workers reproduce every prior emitted field except elapsed seconds, including retained hashes, summaries, complete metadata/telemetry and target-call counts. Disabled counters are zero. The unchanged production kernel already has a thread-local workspace cache and Rc<State> ring; generic buffer pooling is not a new candidate.

Across four chains with1,000 warmup and4,000 retained transitions each:

| Target | Metric | Allocation requests | Gross requested GiB | Requests per transition |
|---|---|---:|---:|---:|
| Direct banana | identity | 8,071,366 | 9.395 | 403.6 |
| Direct banana | adaptive diagonal | 3,250,019 | 3.923 | 162.5 |
| Latent banana | identity | 474,493 | .216 | 23.7 |
| Latent banana | adaptive diagonal | 482,421 | .238 | 24.1 |
| Severe funnel | adaptive diagonal | 927,510 | .842 | 46.4 |

Requests include alloc, alloc_zeroed and realloc. Requested bytes sum gross allocation and reallocation sizes; they are neither peak/live memory nor unique bytes touched. Instrumented elapsed time is not a benchmark. The measured interval is Sampler::run, including warmup, returned sample storage and telemetry, excluding post-run observable summaries/JSON. No statistical improvement or competitive advantage follows from these counts.

Four additional prefix workers (direct/latent diagonal,1/1,000 retained draws) match preserved4,000-draw prefixes exactly, including final step/mass and actual nonretained target calls. The1,000-to4,000 slope is146.821 allocation requests per retained draw for direct banana and21.010 for latent. Estimated fixed residuals account for27.72% and30.32% of requests at4,000 draws. The residual includes startup/warmup, storage-capacity differences and other fixed costs; it is not an exact phase partition. Thus warmup trace storage alone cannot explain most retained-path allocations.

Source review also confirms that reverse schedule vectors and trace-event collections exist, but this audit does not identify their shares or prove allocation time dominates. Previous kernel_efficiency_v1 and WORK-PROFILE-REPORT already cover major statistical-rule/call-count alternatives; do not reintroduce them as novel optimizations. The next reviewed step is bounded component attribution in an isolated production-source copy: label allocator requests around state-pool acquisition, reverse schedules, histogram growth, traced/untraced tree construction, integration and turning predicates, then require exact trajectory/work parity. Only after identifying the source should an optimization be tested with uninstrumented timing and fresh validation. Keep public diagnostics, safety checks and selection/RNG laws intact.
