# Same-target market reference cost panel

Status: frozen and launched on 2026-10-28, supervisor PID 20297. Nine worker,
serialization and queue checks passed in the pinned AWS runtime. Panel SHA-256:
`58df0a15d184d4bc9e791c7c4c874a57a95d33c215e0449792ef8d5f5feadb3e`.
Forty-eight external seeds beginning at 704030000 had no exact-token collisions
in 1,345 primary source records; this is not a universal historical audit.

Use the existing validated Stan target and pinned nutpie/BridgeStan runtime on
all 24 inherited market windows. Four chains per fit use 4,000 warmup and 8,000
retained draws, matching the declared blocked precision schedule. Preserve full
latent draws, warmup and sample statistics, divergence indicators, compiled
library provenance and source/runtime bindings. Reserve distinct interoperable
sampling and initialization seeds for each window before launch.

Fit limits: 1,800 seconds, 4 GiB RSS and 1 GiB output. Run at most four fits
concurrently on disjoint four-core groups. Stop admissions under resource
pressure and retain all 24 denominator slots; no retries or selective extensions.
Disk admission requires 8 GiB free before the campaign and stops new fits below
4 GiB. The outer campaign is bounded at 13,000 seconds, 22 GiB RSS and 8 GiB
sampled output. Launch followed verified redundant-copy cleanup; receipts retain
the exact paths and restored S3 version. The short blocked run's raw chain tree
was archived before reclamation; its inputs, reports and sources remain online.

Measure compilation and sampling separately, as well as full monitored elapsed
time and output serialization. The worker currently compiles in an isolated
workspace for each fit. Such duplicated compilation must not be silently charged
as an intrinsic cost of NUTS while assuming ideal reuse for the specialist.
Report the actual execution and separate sampling-time observations; an optimized
amortized comparison still requires demonstrated compiled-model reuse. Neither
equal draw counts nor passing diagnostics alone establishes equal accuracy.

Keep the original extended references as fixed comparison evidence, including
their two failures. The new fits are competitors, not automatically authoritative
truth. Analyze all 254 coordinates, divergences, predictive discrepancies and
separate Monte Carlo errors. Compare diagnostic adequacy before efficiency.
No posterior, predictive or economic claim may be rescued by dropping a failed
window. Inputs are development-exposed; untouched validation remains separate.
