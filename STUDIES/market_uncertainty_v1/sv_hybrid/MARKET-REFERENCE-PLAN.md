# Same-target market reference cost panel

Status: worker implementation preparation; not frozen or launched.

Use the existing validated Stan target and pinned nutpie/BridgeStan runtime on
all 24 inherited market windows. Four chains per fit use 4,000 warmup and 8,000
retained draws, matching the declared blocked precision schedule. Preserve full
latent draws, warmup and sample statistics, divergence indicators, compiled
library provenance and source/runtime bindings. Reserve distinct interoperable
sampling and initialization seeds for each window before launch.

Fit limits: 1,800 seconds, 4 GiB RSS and 1 GiB output. Run at most four fits
concurrently on disjoint four-core groups. Stop admissions under resource
pressure and retain all 24 denominator slots; no retries or selective extensions.
Complete disk admission and the outer campaign containment review before launch.

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
