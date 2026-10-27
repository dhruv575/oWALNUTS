## Proposed E61 — Fresh prior-predictive resident validation

32 independent prior-predictive streams,250 initial observations and32 fixed-windowK400 updates each; no truncation, replacement, rerun or outcome-selected exclusion. All1024 candidate,1024 NIG and1024 privileged-current-latent-oracle scores completed. All eight independent4x4000 references met frozen reliability diagnostics (maxRhat1.000705,minbulkESS6009.6,mintailESS6855.4,zero retained divergences).

Candidate PIT mean0.51039,95% stream-cluster interval[0.49370,0.52796]; uniform target lies inside the frozen19-grid descriptive PIT band. Candidate-minus-NIG logscore+0.15458nats [0.08527,0.24145]; candidate-minus-privileged-oracle−0.04484 [−0.06582,−0.02572]. Largest candidate/reference PIT/logpdf gaps0.0009365/0.013733nats; the largest logpdf gap has candidate/reference MCSE0.006311/0.002192. No new two-SE gate or universal posterior claim.

Retained sampler telemetry:0divergences across1,638,400 warm and25,600 initial retained transitions; no native initial-chain warnings,128guard checks/0restarts. Warmup remains explicit:365divergences,12,771maximum-depth stops,364refinement-exhaustion stops and1024recoverable zero-density evaluations in128,000 discarded transitions. No retained adverse events of these types.

Supplemental observed-label update latency median0.2571s/P95 0.5105s/max1.0478s, excluding initialization/persistence/imports/integrity; whole32-update candidate job median16.45s. Full73-job campaign806.09s,2.041GBpeak sampledRSS,all processesdrained. No quantile roots in this path. All2466 archive hashes and18,745 postrun source/runtime bindings verified; AWS stopped.

This supports short-run implementation/calibration under the matchedSV model. It does not resolve WP96 long-horizon failure, demonstrate profit/market value, beat strong rollingStudent-t/EWMA baselines, or establish deployment readiness. See STUDIES/prior_predictive_validation_v1/README.md and PROTOCOL-FINAL.md. ArchiveSHA16854d8642d9df2e143e25b02dfc409329d85214c288a02d3fd37fd9b9e1378d; authorizedmanifestSHA926a0b2b75c7f068ee218d1d6354d8e9947cf64d3a710fc4d8a0ce462fe657a8.
