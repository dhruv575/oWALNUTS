# Full-shape plus automatic fallback: broader screen v4

Frozen before sampling, 2026-10-30. This explicitly changes v3's no-block fallback
from frozen diagonal to automatic adaptation. It does not alter prior results.
Selected blocks use unchanged v3 full-shape reconstruction. Nonfinite probes or
installation failures are preserved as failed candidates, not silently retried.

Targets fixed from source/reference inventory: arma-arma11, arK-arK, sblrc-blr,
eight_schools-eight_schools_centered, garch-garch11, gp_pois_regr-gp_pois_regr.
All dimensions <=16, archived reference exists. Qualify references with rank
Rhat<=1.01, minimum bulk/tail ESS>=400 before interpreting performance. Presence
of a reference is not proof of quality. The proper-prior Gaussian regression may
still admit cheap conditional/quadrature inference; do not assume an MCMC use case.

Four fresh seeds929100001--929100004, four PCG64 uniform[-2,2] starts each. Shared
pilot250 warmup+100 discarded draws. Probe16 saved states at two steps, 64*d
target calls. Then candidate, adaptive dense and adaptive auto share pilot final
states, seed+100000,750 warmup+2000 retained draws. If no block qualifies, candidate
runs exactly the auto arm; check complete non-timing result equality and charge
candidate's extra probes. Invert and symmetrize selected covariance; require SPD
and inverse residual<=1e-7. Keep all discovery thresholds, counts and steps frozen.

Same reference-functional accuracy gates as MODEL-SCREEN: Rhat<=1.01,
bulk/tail ESS>=400, no retained divergence, max mean discrepancy<=4.5 combined
MCSE and <=.1 reference SD, relative SD error<=.1. Every arm pays pilot calls;
candidate additionally pays probes. Failures/timeouts count; no seed replacement.

Small continuation screen, not general validation: require no paired accuracy
loss relative to auto on any model; at least one nonconjugate target must have
all four candidate/control cells qualified and candidate geometric-mean minimum
bulk-ESS/total-call ratio>=1.2 versus BOTH dense and auto. Report every model,
worst paired ratio, reference failures and no-block overhead. Any survivor needs
larger independent replication and strong model-specific/gradient-based baselines.
No novelty or actual-usefulness claim from this screen alone.

96 jobs maximum, each180s/2GiB sampled RSS/64MiB output, sequential four-thread
samplers. Durable compressed per-job copies with hashes; originals on dedicated
tmpfs; archive+exact-version restore. Production and defaults unchanged.
