# Execution and serialization audit

The initial build wrapper was launched with system Python, which lacks psutil. It failed before invoking Cargo or sampling. The empty build01 directory is retained. Build02 used the existing research virtual environment; release build and finite-difference/change-of-variables test passed. All sixteen predeclared fits completed and drained their process groups.

The frozen analysis script correctly rejected nonfinite diagnostic values, but its strict JSON writer then refused NaN Rhat values from constant tail indicators. Preserve that original script and its source hash. The corrected analyzer changes only final serialization: nonfinite floats become JSON null, after all qualification decisions have been computed. No thresholds, seeds, draws, diagnostics or gates change. Constant tail features remain failures. This is an output repair, not a statistical relaxation.

After the verified archive was closed, the checked-in build wrapper's trailing blank line was removed to pass whitespace review. The archive retains the executed pre-formatting wrapper; no executable statement changed.
