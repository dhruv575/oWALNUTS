# Native baseline qualified after preserved integration failures

Pinned nutpie0.16.11 is installed in a separate local environment; the prior
WALNUTS validation environment and failed continuation gate remain unchanged.
Native regression qualification now passes all three modes. This is backend
qualification on one exposed seed, not independent algorithm or application evidence.

| Native adaptation | max Rhat | minimum bulk ESS | minimum tail ESS | retained divergences | max mean error/refSD | max relative SD error |
|---|---|---|---|---|---|---|
| draw_diag |1.00142|1897.63|2859.45|0|.01994|.04089|
| diag (Fisher) |1.00336|1371.91|1915.06|0|.02937|.01358|
| low_rank (Fisher) |1.00073|8978.42|6223.93|0|.01588|.01211|

All combined-MCSE mean discrepancies are below1.083. Low-rank uses cutoff2 and
gamma1e-5; four chains/cores,1100 warmup and2000 retained draws, seed929800001,
target_accept.8,maxdepth10. Native default initialization is not exactly paired
with WALNUTS starts. Full target-call counts are not instrumented; native step
diagnostics remain preserved without relabeling them as complete target calls.

Full invocations took7.713/7.808/7.912s; sampling plus result conversion took
.14994/.14614/.15660s, respectively. Imports, model construction and remaining
worker operations lie outside the latter clock. Do not compare that clock with
WALNUTS full-invocation times or infer kernel speed from startup overhead. A
future comparison must align timing scopes and provide both operational and
post-startup measurements. These are single-run qualification times only.

## Preserved failures and model equivalence

nativepreflight01 failed before sampling: nutpie rejected STAN_THREADS=false
in the archived library. Its21-member local archive is verified (SHA256
51a6b44168cdaf12b4e10a23fe6ed9d385e5a5d54004ee5b1a081b344f41bc90).

An exact-byte copy of the Stan source was rebuilt with BridgeStan2.9.0,
Stan2.39.0, g++15.2.0,STAN_THREADS=true. The original library was retained.
Old/new library comparisons at64 frozen points had zero observed density and
gradient difference and identical unconstrained parameter names. New library
SHA2569c69b04214fb5a2e539d90509e981beb31851592e4cf1ab2340741afffdb6e77.
Build39.949s,peakRSS1,962,004,480bytes, whole build238,068,634bytes; group drained
within the180s/2GiB/1GiB build limits. Its15-member archive includes the official
source release tarball and passes read-back verification (SHA256
94bf80f69829fe101d56d30f6949df7ff5a981ffc0e33813b7a3dd09c6a84914).

nativepreflight02 sampled but its adapter then treated a Dataset as a DataTree
during serialization. No accuracy results were recovered from that attempt.
The27-member failure archive is verified (SHA256
f0d395a0d48eac678ccb4302d23b850ad58ec9ce57a83fb005f5bc0ef2c21766).

nativepreflight03 fixes only that dispatch, reusing the same seed and gates.
All workers drained. Its41-member archive contains raw draws, compressed native
diagnostics, settings, environment/source hashes and the pinned wheel; every
member was read back and verified (SHA256
20bcf6976f5fc04404a46e8e34b91ed059ab08db1c8fa15a96ea2f352615974b).
All archives are local; no S3 or off-device backup is claimed.

Next qualify threaded builds for the other five targets, then freeze a stronger
native comparison with matched timing scopes and honest call instrumentation.
Do not retune the failed score threshold or convert this backend success into
a WALNUTS advantage claim. Deployment and trading remain outside this work.
