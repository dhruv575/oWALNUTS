# Name-free selector preflight, 2026-10-30

V1 FAILED one analytic gate: inclusion-maximal blocks absorbed an independent
coordinate. The resulting covariance was still correct, but block discovery
was wrong. V2 explicitly requires a connected normalized-precision graph;
both original and revised protocols, sources and results are preserved.

V2 passes seven analytic checks and 120 saved-state permutation checks. It
identifies the coefficient blocks in all six exposed regression cells, and
selects no block in all six GP/GARCH cells. No coordinate names enter selection.
Maximum permutation discrepancy is below 3e-13. Independent, indefinite,
ill-conditioned, rotating and derivative-inconsistent analytic probes fall back.
Unit equivariance was checked for EXACTLY proportional curvature only; the
trace-normalized averaging rule need not be unit-equivariant for changing shape.
The analytic Hessian fixtures are not posterior sampling or finite-difference
accuracy tests. Probe numerical checks reuse the earlier model audit.

Both jobs drained, inputs unchanged, about .33 seconds supervised each, ~39 MB
sampled peak RSS. Reusing saved Hessians costs zero additional target calls;
online use would pay for probes and must include that cost. No production sampler
change, speed claim, novel contribution claim or useful application follows.
Next work: freeze online timing, installation and fallback details; integrate
in an isolated source copy; verify known-target posterior fidelity, then fresh
broad seeded comparisons against automatic, dense and diagonal controls.

Complete archive: 17 members, 459,087 bytes, SHA256
f235fbabe419ac464ee503942a70f1b81d3daf644a930ae4c5081b7b231eab83.
Exact-version restore/member verification passed; see selector_archive_complete.
An earlier 14-member archive was made before the download finished. Its hashes
verify its contents but it is INCOMPLETE and superseded; retain its receipt as
an operational failure. The final archive builder asserts all 17 files and
checks input hashes against both supervisors before archiving. Raw inputs also
remain in the verified preceding metric audit archive and durable remote copies.
