# Fresh hybrid validation, frozen 2026-10-30

Policy developed on broad01 only. Evaluate leave-one-chain-out affine score
prediction in every direction. Prefer fixed dense Fisher iff all four worst
directional R2 values are strictly positive and its numerical fit installs safely.
Otherwise use unchanged v4 stable-full-shape blocks, with automatic fallback.
Invalid/rank-deficient gate inputs decline Fisher. No model names enter policy.
No threshold search or policy changes during validation.

Six targets unchanged: ARMA, arK, sblrc, centered eight schools, GARCH, GP Poisson.
Fresh seeds929300001..929300016, four chains uniform[-2,2]. Shared discarded
pilot250 warmup+100 draws; stages750 warmup+2000 draws, seed+100000, identical
pilot last states. Five arms: hybrid, v4, unconditional Fisher, adaptive dense,
automatic. Compute400 pilot scores and64d finite-difference probes; record both
and charge hybrid both even if one branch is unused. V4 charged probes only;
Fisher charged scores only. All arms charged pilot and all own fitting time.
Use qualified80-digit Fisher estimator, gamma0; disclose expensive numerics and
make no optimized-baseline wall-time claim. All fixed metrics SPD with symmetrized
inverse and ||C M-I||<=1e-7. Failed numerical fit counts as failure for Fisher;
hybrid uses its explicit v4 fallback. Preserve failures without reruns.

Same reference gates: rankRhat<=1.01, bulk/tailESS>=400, retaineddivergences0,
mean error<=4.5 combined MCSE and .1 referenceSD, relative SD error<=.1.
Continuation gate requires: no paired hybrid accuracy loss vs auto or v4; at least
one non-Gaussian-model target (ARMA or GARCH or GP or eight schools) with all16
hybrid/auto/v4 cells qualified, paired geometric ESS/total-call ratio>=1.2 versus
both auto and v4, with95% bootstrap lower bound>1 for both; and no qualified
target's hybrid/Fisher paired geometric ratio below .9. Per-target intervals
are exploratory, not simultaneous inference or general superiority. Failed
comparisons get no ratio credit. Preserve eight-schools failures; no goal-complete
or application claim from this gate alone. Six-model family is not broad coverage.

Run in four immutable4-seed chunks. Each fit and sampler bounded180s,2GiB RSS,
64MiB sampled output. Each chunk source/input hashes, jobs, raw draws, scores and
probes are archived and exact-version restored before reclaiming redundant gzip
copies. Root floor1GiB; tmpfs cap6GiB; stop admitting work below floor. No existing
jobs restarted from missing observers. Archive/push completed checkpoints during
validation. Unrelated edits untouched; no production/default changes.
