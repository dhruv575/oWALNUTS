# Exact linear population target preflight

No inference until parity passes. Preserve the ODE implementation unchanged.
Audit both optimized modes, global/local exchanges of 32 archived retained states,
and 12 nearly equal-rate configurations (signed gaps 0, 1e-10, 1e-6, 1e-3).
Compare analytic gradients against tight ODE gradients: max scaled coordinate
error <= 1e-4; log-density offset spread <= 1e-5. Check central finite differences
at both modes and all equal-rate configurations: max scaled error <= 1e-4.
Check value-only and value/gradient log densities agree within 1e-10 relative.
Time equal numbers of gradient calls with the same Python/ctypes overhead,
report target acceleration only, not algorithm/application improvement.
Bound preflight to 180 seconds, use one BLAS thread and tmpfs artifacts.
