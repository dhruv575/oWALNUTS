# Remaining native target build qualification

Freeze before execution. Reuse the verified BridgeStan2.9.0/Stan2.39.0 source
cache from threaded_build01; compile unchanged source for ARMA,arK,centered
eight-schools,GARCH and GP-Poisson with STAN_THREADS=true,make-j1. Preserve the
original nonthreaded libraries. No model, prior, data or transform edits.

Each compile+parity worker180s/2GiB/1GiB sampled whole-cache output bound;
one worker at a time. Both WSL build filesystem and Windows workspace need1GiB
free. Reuse existing toolchain; no repeated download or parallel builds.

For each target use64 fixed points chosen without replacement from the saved
localscaled01 seed929600001 pilot, RNG929899998. Verify pilot/source/data hashes,
matching unconstrained parameter names, new model reports STAN_THREADS=true,
centered log-density difference<=1e-6 and scaled gradient error<=1e-7 against
the original. Preserve points, results, build flags and library hashes. This is
functional build qualification on exposed positions, not fresh sampler evidence.

If a build or parity check fails, preserve it and do not admit that target into
native sampling. Complete other independent bounded qualifications; record the
failed target rather than silently dropping it from a later comparison. Each
successful target's raw and summary evidence must be archived and read back.
Any compiler/limit change requires an explicit recorded build amendment and
new output directory, never overwriting a failure. Future paired engine studies
must use the same qualified model library on both sides.
