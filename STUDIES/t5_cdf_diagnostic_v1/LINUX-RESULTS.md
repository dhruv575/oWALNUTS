# Linux same-draw arithmetic replay result

The exact t5 implementation reduced full-return summary arithmetic from roughly
2.20s to0.66s on the original host, with unchanged posterior draws and GH64/128.
All24 fixed calls passed; every paired quantile differed by at most6.94e-18 across
both quadrature orders. This measures arithmetic only. The0.66s arithmetic cost
alone remains above a0.4s complete-update target; no fused total is claimed.

| Tick | SciPy median seconds | Exact median seconds | Median paired speed ratio |
|---|---:|---:|---:|
|1|2.2052|0.66031|3.3387|
|2|2.2104|0.66035|3.3479|
|3|2.1986|0.66168|3.3246|
|4|2.2109|0.66039|3.3479|

All12 paired ratios ranged3.2983–3.3512. Full per-call roots, residuals, bracket,
work, cached bytes and cross-order checks are retained in linux-evidence/result.json;
linux-analysis.json records every pair and differences across both GH rules.
The frozen schedule reversed/interleaved ticks relative to the earlier local run.
No repetitions were dropped, and there were no retries, sampling or node changes.

Linux tests passed the same244017-point grid, IEEE/known/symmetry/monotonicity and
independent quadrature checks. Source/input/package/native pins passed before and
after. The separately captured142 Python/scientific binary hashes also remained
unchanged. Exact prefix and symlink-preserving interpreter came from the original
isolated resident environment: Python3.12, NumPy2.4.6, SciPy1.18.1, numba0.67.0,
llvmlite0.49.0. CPU affinity0–3, BLAS/OpenMP threads1; idle context had load0.21
and no other research workers. CPU/runtime details are archived.

The one run started2026-10-27 17:57:20.760090UTC and ended17:57:56.791430UTC:
36.03s external wall, including imports/preflight1.224s, t5 import/JIT0.583s (a
subset of import time), tests0.158s and all24 arithmetic calls. It stayed within
180s. Supervisor1374 and owned process group1376 were independently absent at
17:58:25UTC; no descendant computation remained. No execution cap fired.
Parent retains AWS lifecycle control; this agent did not stop/restart the box.

The frozen upload bundle was205560bytes, SHA
9115a075cb51bff8231e5fccc6e354a46846545319fb02cd03d46f04931ab7ad.
Retrieved archive was220039bytes, SHA
2b973b10c528a41d3dbf59d16072ddddc4866f2fdb11e2425c6feae5c5be5ce7.
The latter was downloaded, hash verified, and all17 enclosed manifest entries
verified locally. Sources, runtime inventory, input arrays, logs and results are
preserved under linux-evidence. linux-manifest.json pins the exact executed
filesystem bytes; this avoids historical Git newline normalization. Final study
checksums are separate from the unchanged original local15-file manifest.

Read-only pre-execution review approved the plan/supervisor and mathematical
identity. All evidence concerns a fixed four-tick development fixture; numerical
identity is not a posterior-calibration, trading or profitability qualification.
