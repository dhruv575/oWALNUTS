# Final scientific protocol: prior-predictive validation v1

**Scientific settings frozen; campaign launch requires parent authorization of the exact bound manifest.** The corrected literal full-worker readiness completed all three stages. Earlier DRAFT.md and PROTOCOL-PROPOSED.md preserve design history. The bound production manifest records actual immutable source/runtime paths and checksums. No study outcomes informed this freeze.

The question is whether the current fixed-window resident approximation yields calibrated, numerically valid predictive distributions under its own known model. This is an implementation/calibration study, not market-value or deployment evidence. NIG is a cheap diagnostic comparator; success against it does not establish superiority to rolling Student-t or EWMA alternatives.

## Fixed observations and inference

Generate 32 independent streams with exactly283 latent states/returns each. Parameters are mu~Normal(2log(.005),1), log_sigma~Normal(log(.2),.5), beta~Normal(0,.002); rho=.95 and nu=5. Initial latent is stationary. Each stream's data RNG draws parameters first, then283 Gaussian innovations, then283 Student-t5 innovations. No truncation, resampling, replacement or favorable selection. Overflow/nonfinite generation preserves acquired parameters/seeds/error and fails that stream.

Initial fit uses y[0:250]. For update j=1..32, observe y[249+j], condition on y[j:250+j], score label y[250+j]. All1024 planned origins remain, including failures. The oracle knows true parameters and current h[249+j], and integrates the NEXT innovation; it never receives future h[250+j]. The oracle has privileged information and is not required to lose or win at every individual label.

Candidate is exactly four-chain resident K400 with frozen boundary remap, appended innovation0 and mass1, no pooling or re-adaptation. Initial fit1000 warmup/200 retained at deterministic prior-center positions; same reviewed depth10/refinement8 tuning, default declared initial trapped-chain guard, full guard/seed/cost telemetry. A failed transition poisons that stream; no retry. All chains are retained.

Observed-return scoring uses the fixed evaluator, GH128 primary corroborated by GH64, both absolute PIT and logpdf differences <=1e-6. Same exact Student-t5 CDF implementation, full joint(mu,log_sigma,beta,h_last), stable density evaluation and inverse-scale Jacobian. No quantile roots, score clipping or probability repair. Numerical failure is unavailable evidence.

Baseline is the fixed NIG lag regression with a0=3,b0=.0002, prior covariance100s²I,249 mature pairs from the same250-return window, training-only lag standardization and latest-return forecast covariate. Candidate, baseline and oracle availability are independent. Side scores run on successfully generated streams even when candidate initialization failed.

## Independent corroboration

Fixed eight sentinels (stream,tick): (0,1),(4,32),(8,1),(12,32),(16,1),(20,32),(24,1),(28,32). Nutpie0.16.8/BridgeStan2.9 public API, separate compile per fit inside bounded workspace, four chains,2000 warmup,4000 retained. Options target_accept=.8,maxdepth10,store_mass_matrixTrue,low_rank_modified_mass_matrixFalse,transform_adaptFalse. Model seed is reserved sample base+1; opaque engine-internal derivation is not claimed independently proved.

The independent-engine development preflight established six literal N12/N250 target/gradient parity cases, full float64 joint extraction and current terminal-latent reconstruction. It did not establish long-fit precision or all-stream reliability. The full worker readiness must additionally exercise the exact scoring/ArviZ path in the newly pinned unified environment.

Descriptive reference reliability: all four-chain draws finite, no retained divergences, rank Rhat<=1.01 and bulk/tail ESS>=1000 for globals/endpoint and observed-return PIT/integrated density, PIT mean MCSE<=.005 and delta log-density MCSE<=.01. Log-density MCSE targets log(mean integrated density), not mean per-draw logdensity. Candidate matching PIT/delta-density MCSE uses its own saved chain/draw arrays at the same eight sentinels. Candidate precision failure does not erase valid reference evidence; integrity failures are reported separately. No reference extensions, replacements or chain exclusions. Passing eight sentinels cannot certify1024 approximations.

## Reporting and resource accounting

Report full32-stream/1024-origin availability, stage-specific failures, interrupted and never-started rows. Use10000 bootstrap resamples of whole independent streams with one fixed reserved seed and paired resamples across arms. Full-panel logscore means/intervals and PIT ECDF envelopes are undefined if any relevant origin is missing. Available-case summaries remain explicitly conditional with exact counts. PIT summaries include mean, second moment,19-point ECDF, ten bins,5% tails and exact0/1 counts; stream-level values and leave-one-stream-out sensitivity remain visible. No omnibus qualification verdict.

Fixed schedule has32 candidate jobs,32 side jobs,eight reference jobs,one report job. Accepted fixed caps, confirmed from literal development overhead before study outcomes: candidate1200s total/60s per stream; sides600s/60s each; references900s/180s each (including independent compile); report120s. Internal campaign2880s, external wholecampaign3000s including final integrity processing. Each process cleanup allows up to5 additional seconds TERM/KILL; external monitor covers nested jobs and orphan/new-session descendants. Sampled aggregateRSS4GiB, campaign output1GiB, cores0-3 and BLAS/OpenMP threads1. Resource failure is retained, never repaired by dropping difficult cases. These bounds may yield incomplete evidence and do not promise successful completion.

All source/native/runtime/SDK bindings are checked before and after. Every generated y/h array, candidate compact/score array and independent reference draw/score array is hashed. Final validator requires the full planned ledger and identities, not favorable results. Exact production seeds remain those in SEED-AUDIT.json and its documented bounded supplement; development seeds are separately audited and never substitute for production seeds.

## Development admission evidence

Corrected literal readiness completed in50.73seconds total: fresh candidate process25.59seconds for initialization and32 K400 updates; side process3.06seconds for32 NIG/oracle scores; independent reference process19.56seconds including compile,4x4000retained draws, evaluator and ArviZ. Peak observedRSS2.011GB; all owned processes drained and source/SDK/runtime bindings remained unchanged. The literal reference met the descriptive diagnostic thresholds. These timings support admission bounds but do not guarantee completion across untruncated prior-predictive parameters.

The earlier literal smoke failed when a bound chain_warnings method was stored instead of its return value; that attempt is preserved. The corrected adapter invokes the method and retains its structured records. No study RNG or study data were consumed by either development attempt.

Whole-job timings include fresh interpreter/import/JIT, integrity, persistence and initialization costs. Report them separately from per-update candidate_total_seconds and native sampling. Observed-label PIT/logpdf evaluation omits quantile root finding and is not the previously measured complete return-quantile update.

Before launch, archive the exact production manifest bytes and SHA256 in a separate launch record, set the manifest read-only, and verify the same SHA after completion. Only the execution authorization field may change between pending and authorized manifests; preserve both identities.
