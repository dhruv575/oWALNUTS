# Latest build versus conservative NUTS

Frozen before new results: rebuild committed source e7139bed in release mode,
using its locked dependencies. Record source archive and extension SHA256,
compiler, build flags, Python package paths and versions. Preserve the failed
offline build attempt. Isolate the resulting extension from installed WAL.

Cases: existing mixed dataset and two deterministic stress variants. For groups
whose original n >= 1000 multiply both n and y by 10 or 100; retain all other
counts and priors. These are likelihood-concentration stress tests, not new
independent datasets or observed business outcomes. This increases the disparity
in information across groups without changing their observed rates. Recompute
the independent quadrature reference with the existing convergence/domain gates.
Reference failures block accuracy claims for that case; retain them.

Compare installed WAL, rebuilt WAL and nutpie0.16.11 NUTS. All noncentered,
four chains on one pinned CPU, 1000 warmup, depth11; WAL acceptance .9 and
max_error1, NUTS acceptance .999. No retuning on confirmation seeds.
Four fresh seeds per case: 956800011..14, 956800021..24, 956800031..34.
Each uses separate 4000/8000/16000 draw budgets. Rotate engine order by seed.
All 108 fits run serially. Report all accuracy/health/precision gates, failures,
target evaluations, sampling and full-worker time. Count cumulative cost through
first passing budget, and censor runs with no passing budget. A fixed-draw time
ratio alone is not a time-to-accuracy claim. Four seeds remain exploratory.

Use existing EC2 with executable RAM staging, <=512MiB evidence, <=2GiB per
worker and <=900 seconds per fit; build <=3GiB output, <=8GiB RAM and <=900s.
Do not install into or alter existing environments. Preserve source, raw draws,
failures and verified archives locally before reclaiming staging. No root-disk
expansion; monitor root disk separately as well as RAM staging. No deployment.
