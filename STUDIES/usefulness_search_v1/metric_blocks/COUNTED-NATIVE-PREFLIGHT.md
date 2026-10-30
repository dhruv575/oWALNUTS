# Native target-evaluation counter qualification

Freeze before execution. Add a thin shared-library wrapper around the qualified
threaded regression library. Forward BridgeStan2.9.0 C-ABI value, gradient,
Hessian and Hessian-vector-product functions unchanged, counting attempted
calls with relaxed atomic counters. Other symbols resolve from the unchanged
dependent model library. Count failures as attempts. Record the four counters
separately; do not pretend Hessian or value-only work equals a gradient.

Verify each of the four explicit API calls increments its own counter and
preserves returned values. Then four model instances concurrently perform64
gradient calls each; require exact256 gradient calls and zero others, and
unchanged values/gradients. Same compiled model/data and fixed64 points from
threaded_build01. Reset only before a measurement, never during active calls.

Replay all three nativepreflight03 arms using the same exposed seed/schedules
and only the wrapper library substitution. Reset before native model construction;
read counts after sampling. Require exact retained unconstrained draws and
divergences against saved uninstrumented results. Require positive gradient
counts at least the summed warmup/retained native step diagnostic; preserve the
observed difference as initialization/other-work evidence, not an assumed formula.
Native Hessian/HVP counts must be zero for gradient-only comparisons. Report
value-only calls if present. This proves counter behavior on tested paths, not
general interception of arbitrary internal target implementations.

No new statistical replication or performance advantage claim. Preserve every
failure. One whole worker180s/2GiB/64MiB, including its subprocesses and full root
output; compiler-j1, four native chains/cores, BLAS1. Archive source, ABI header,
linked model hash, explicit-call and sampling parity evidence; read back members.
