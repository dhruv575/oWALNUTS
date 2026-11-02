# Native grid followup

The Python grid implementation measures about 8x faster than the original
compiled Stan gradient at N=200 on the fixed probes. Implement the same
symmetric-root formulas in isolated native code to avoid Python callback cost
inside NUTS. Preserve 1e-10 jitter and fail on nonpositive eigenvalues.
Before sampling, check density/gradient against the validated Python grid on
fixed and random points, including finite differences. Require the original
1e-5 density and 1e-3 normalized gradient tolerances. Do not alter the target.

If numerical checks pass, run native NUTS with the same 4 chains, 1000 warmup,
2000 retained, acceptance .99, max depth 12 and original two spatial seeds.
Coordinates and initialization differ; physical summaries and convergence
must be compared. Count setup, prediction/diagnostics and sampling separately.
Use at most eight CPUs once earlier native controls finish; 900 seconds per
job and original resource limits. This remains a pilot because the combined
independent spatial reference is unqualified.
