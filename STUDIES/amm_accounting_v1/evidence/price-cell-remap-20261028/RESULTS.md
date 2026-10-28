# Rolling initialization transform admission

The local independent physical-path tests passed for T=2,12,250 and
rho=-.8,0,.95, with four chains each. They reconstruct volatility paths using
the direct h recurrence, and prices using logistic coordinates; all overlapping
paths are preserved. Tests also check copied metric blocks, explicit unit mass
for mixed/new coordinates, zero appended innovations, input non-mutation and
rejection of incompatible endpoints and invalid metric entries.

AWS deterministic native checks passed at 12 remapped chain positions across
T=2,12,250. Maximum absolute density error versus the analytic implementation
was 2.274e-12; maximum gradient error was 5.685e-13. Mutating the caller's
cell arrays after compilation left native evaluations unchanged. Five exact
source hashes in REPORT.json were verified against the uploaded source archive
and preserved here. Runtime was 1.778 seconds under a 60-second timeout,
single-core affinity and 4 GiB address-space limit.

This admits the deterministic initialization transformation only. No live
WarmSession retarget sampling was performed. Next check resident retarget
against a fresh session under the documented matching seed schedule, then
perform a bounded warm-versus-cold reference experiment. The boundary initial
price must be common across chains and explicit; market semantics remain open.
