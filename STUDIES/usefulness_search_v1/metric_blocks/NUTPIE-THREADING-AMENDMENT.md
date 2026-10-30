# Native backend build amendment

nativepreflight01 failed before sampling in all three arms: nutpie requires
STAN_THREADS=true, while the archived model has STAN_THREADS=false. Preserve
the failure and its verified21-member archive. This is a bridge/build failure,
not sampler accuracy evidence. The original model libraries remain unchanged.

Rebuild an exact-byte copy of the regression Stan source with BridgeStan2.9.0,
Stan2.39.0 and STAN_THREADS=true in a separate local build directory. Preserve
the official release archive hash, compiler version, model source hash, compiler
flags and resulting library hash. Download/extract/build is a separate bounded
job:180s,2GiB RSS,1GiB whole-build-directory sampled disk cap, make-j2. All source
and output live on disk; preserve failures. Sampling limits remain180s/2GiB/64MiB.

Before retrying the backend, compare old/new libraries at64 fixed regression
points (seed929899999): beta=1+.001Normal and log_sigma uniform[-.4,.4]. Require
matching unconstrained parameter names, centered log-density differences<=1e-6,
scaled gradient error<=1e-7. Verify the new library reports threading enabled.
This is a compilation-equivalence check, not a new posterior or new study.

Only after equivalence passes, run nativepreflight02 with the exact previous
sampling seed, schedules, modes and reference gates. The seed is exposed for
backend qualification; no independence or fresh performance claim. Record the
new library provenance explicitly rather than claiming original binary identity.
