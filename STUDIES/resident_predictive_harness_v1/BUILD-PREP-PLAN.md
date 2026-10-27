# Isolated Linux native preparation ? authorized bounded work

Preparation only; no representative sampling smoke authorized here. Wait for
WP97 agent's explicit successful official-analysis end marker before any install,
compile or CPU-consuming validation. Existing instance only, cores0?3, deadline
20minutes for the entire detached preparation process group. Preserve log/exit
status on failure; no silent retry. Parent explicitly authorized this preparation.

Pin root/native Python source to main commit
4c9320f2a11186a8c86eaf5b0827220677439617. Transfer an immutable git archive containing
Cargo manifests/lockfiles, src, integrations/python and integrations/bridgestan,
and required license/readme metadata. Record SHA256 of compressed archive and all
members before transfer; verify both after extraction. No remote checkout edits.
Build with cargo1.88.0 and maturin1.15.0, --release --locked --no-default-features:
Python extension's Stan feature disabled, root research enabled by dependency,
root candidate-levels10 disabled. Save cargo metadata/tree feature output and
rustc/cargo/maturin versions; hash resulting wheel and native extension.

Use a newly created venv in a unique lane, with no system-site-packages. Install
pinned NumPy2.4.6, SciPy1.18.1, numba0.67.0, llvmlite0.49.0 and maturin1.15.0;
these versions are present in the older callpath environment, but do not reuse its
editable owalnuts or modify it. Save pip freeze. Package installation may fail or
time out; preserve the outcome rather than changing versions after errors.

Install only the freshly built wheel, then verify WarmSession,
refresh_functionals/from_cfunc_functional and expected DEFAULTS, exact extension
path/hash, Python facade hash and actual package versions. No sampler execution in
this preparation. Native compilation and package imports are the only compute.
Use a fresh CARGO_TARGET_DIR; never share current studies' build output paths.

Supervisor must own a new process group, enforce1200seconds (TERM then KILL/reap),
write UTC start/end/PID/exit/timeout and capture combined output. Hard deadline is
also bounded by instance19:35:51UTC backstop minus archive reserve. A finished
build does not authorize the N250/K400 smoke; await parent review/authorization.
