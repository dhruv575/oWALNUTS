# Frozen Linux arithmetic replay plan

One run only, no sampling, no retries, no changed numerical implementation.
Parent restarts and supplies readiness/IP; do not launch before that notice.
Use existing /home/ubuntu/lanes/resident-predictive-build-20261027/env/bin/python
without resolving its symlink. Assert exact env prefix and the pinned native/API
hashes in linux-manifest.json. Packages: NumPy2.4.6 SciPy1.18.1 numba0.67.0
llvmlite0.49.0 owalnuts0.3.0. Record full runtime identity, affinity and CPU model.
All other workloads idle; execution affinity0–3, BLAS/OpenMP threads1.

Use precisely the four saved host (4,400,4) compact arrays, pinned SHA256.
GH64/128, all joint draws, all P5/P50/P95 roots and cross-order checks, tolerances,
chunk512/cache64MiB unchanged. Exact t5.py and processor_snapshot.py retain their
validated bytes. No model/kernel/default changes. Timed scope is return summary
only, including both processor constructions and cross-order checks, excluding
unchanged scale quantiles, native refresh and persistence. Never add these timings
to another run to claim a fused total.

Three paired repetitions. Rep0 tickorder[4,3,2,1], rep1[1,2,3,4], rep2[4,3,2,1].
Within each pair, order exact/SciPy when (rep+tick)%2==0, otherwise SciPy/exact.
This reverses local tick ordering and interleaves paired measurements. Report all
24 calls, per-pair ratios and per-tick medians, not only pooled speedups.

One180second external wall envelope includes Python imports, native/runtime/hash
preflight, JIT and fixed Linux tests, and all24 calls. JIT/import and tests measured
separately; no warmup timings silently discarded. Linux tests repeat the fixed
244017-point CDF/SF grid/branch/IEEE/monotonicity checks and independent quadrature
fixtures; 90-digit checks were validated locally and are not rerun because the
isolated environment intentionally has no mpmath. Thresholds unchanged.

Supervisor owns a fresh process group; at180s TERM then at most3s grace, KILL then
at most2s drain observation. Check group independently of leader exit. Preserve
partial logs/results with planned24 and attempted/in-progress/never-started IDs.
Fail closed if any call, test, input/source hash, runtime pin, or final evidence
check fails; do not relaunch. Preserve failures and report actual remaining groups.
Verify inputs and all executed source hashes before and after. Sources and pinned
manifest committed before parent review/launch. Fresh artifact root, refuse any
existing outputs. Parent retains20minute instance backstop and lifecycle control.
