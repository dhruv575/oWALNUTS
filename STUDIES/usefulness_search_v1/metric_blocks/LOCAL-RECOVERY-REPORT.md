# Local research continuation after budget stop

AWS remains stopped; its USD60 budget action was not overridden. Archived Linux
models and sampler were restored with archive/member hash verification. Local
WSL uses Python3.14.4 and pinned scientific packages; EC2 used Python3.12.
An isolated Intel TBB2020.3.254 runtime resolves libtbb.so.2. Hardware/runtime
provenance differs, so no timing or statistical observations are pooled.

The exposed compatibility preflight passed64 analytic proper-prior regression
checks: centered log-density error1.52e-12, scaled gradient error7.86e-13.
Archived pilot and automatic-stage non-timing outputs replayed exactly. The
stage met all original reference gates (maxRhat1.00182, minimum bulkESS1565.65,
minimum tailESS2133.24, zero retained divergences). Supervision11.25s,
peakRSS256,540,672bytes, final output988,093bytes, process group drained.
This qualifies the environment; it is not fresh algorithm evidence.

Compatibility archive:52 members, SHA256
a2786e73c2c19e36ecff993405c3745c85e7c7854659cd4649dd6cdb8803fe2a.
Archive was read back and every member verified. It is a local copy only.

Before new sampling, LOCAL-SCALED-VALIDATION.md froze seeds929600001--16 and
inherited the full six-target/six-arm protocol, thresholds and continuation gate.
Interrupted cloud seeds remain reserved. Workers independently perform their
policy fitting; measured invocation times include startup, fitting and sampling,
with shared pilot charged, excluding common diagnostics and controller IO.

First two-seed chunk completed84 jobs/72 stages. Verification checked costs,
supervised times, durable gzip hashes, unchanged sources and24 exact selected
branch outputs. Candidate passes2/2 on ARMA,arK,sblrc,GARCH,GP-Poisson;0/2 on
centered eight-schools. All selected candidate branches equal the old hybrid:
no scaled-block branch occurred, so this chunk cannot validate the repair.
GP-Poisson unconditional Fisher failed one seed while the candidate passed both.
These are interim observations, not a completed aggregate or usefulness claim.

Chunk archive:569 members, SHA256
214bea70a7374a942e67ba532bb58ca7be778faa005679af714894791867a43f.
Every member was read back and verified. Remaining seven immutable chunks run
sequentially; an audit and local archive verification gate each next chunk.
All negative results and raw files are preserved. AWS remains budget-stopped.

## Interim checkpoint after four chunks

Chunks1--4 complete:336 jobs,288 matched stages; all source, cost, timing,
durable-copy and branch-reconstruction audits pass. Each local archive contains
569 verified members. Archive receipts for chunks2/3/4 record SHA256 respectively:

    09ccdc53419870af54a35a1a86ab441172e63c2404375fc201fb814fcb186660
    7d1abd6d52900b7e5cf5e4be165d386aaa5a358b86e5bfeae599ffa5f09c3fba
    98edbdd8077214d6ac833dc2a01e6a5e4b2c19ceaf03c32e1d6a0802466fe906

The first fresh scaled-block selection occurs on sblrc seed929600008. Every
comparison arm passes that cell's accuracy gates. Candidate ESS/total-call is
.076897 versus .011539 old hybrid and .074952 Fisher: ratios6.664 and1.026.
Supervised shared-pilot-plus-policy invocation time is1.486s versus1.279s old
hybrid and1.178s Fisher. Thus the call-efficiency gain is not a lower elapsed
time claim; full effective-sample/time comparisons remain necessary. This is
one interim repair case, not a completed aggregate, independent model family,
or application validation. Chunks5--8 remain queued without protocol changes.
