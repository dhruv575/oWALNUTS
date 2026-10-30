# Native evaluation counting and broader model qualification

counter01 passes. The wrapper forwards the four BridgeStan2.9.0 density API
entry points and records attempted calls separately. Explicit value, gradient,
Hessian and HVP calls each increment exactly the corresponding counter and
return unchanged values. A deliberately invalid gradient call is counted.
Four concurrent model instances make256 total gradient calls, counted exactly,
with unchanged values and gradients. No counters are reset during active work.

All three native regression replays reproduce every retained unconstrained
draw and the divergence count from nativepreflight03 exactly:

| Mode | Actual gradient API calls | Reported warmup+retained steps | Difference |
|---|---|---|---|
| draw_diag |78822|78778|44|
| diag |70991|70921|70|
| low_rank |55355|55286|69|

Value-only, Hessian and HVP counts are all zero in these sampling replays.
The differences establish that native step counts omit some gradient work;
they are not attributed to a particular initialization subroutine without
further evidence. These are exposed parity checks, not new accuracy replication.
Counter overhead must be retained in future implementation-level timing results.
The scope is attempted C-ABI target evaluations, not arbitrary internal work
inside a target evaluation.

Whole worker27.560s,peakRSS328,835,072bytes,final output5,336,809bytes; process
group drained within180s/2GiB/64MiB. The46-member local archive includes linked
model/header/source hashes and uninstrumented parent draws; all members read
back and verified. SHA256:
5b79d99804302438e4bb1b8d7cd7a3c747208b1313bc1e3d83c6f7918ce9ef40.

## Remaining five threaded models

ARMA,arK,centered eight-schools,GARCH and GP-Poisson each compiled successfully
from unchanged source, with make-j1/STAN_THREADS=true. All64 selected saved-pilot
points per target had zero observed old/new density and gradient difference,
and parameter names agree. These are functional build checks, not posterior
accuracy tests. The centered eight-schools sampling failures remain unchanged.

Each bounded build drained, took9.54--16.72s and peaked at most1,920,118,784RSSbytes.
The largest whole-cache output measurement was242,546,015bytes. An audit compared
all20,536 regular files in the original BridgeStan release with the reused
toolchain cache; all were byte-identical. This verifies source immutability,
not bitwise reproducibility under another compiler/platform.

The67-member local build archive was read back and verified. SHA256:
bc81ba156771a1438f72dd3bf54f0a9a70be840e4319ed838270d23a99c3d883.
Neither archive is an S3/off-device backup.

NATIVE-COMPARISON-SCREEN.md now freezes the next seven-arm, six-target screen.
It requires generic per-target wrapper qualification before fresh sampling,
actual gradient counts, aligned post-import operation clocks, all original
accuracy gates, and preservation of failures. No comparative advantage or
application success has been established by these integration checks.
