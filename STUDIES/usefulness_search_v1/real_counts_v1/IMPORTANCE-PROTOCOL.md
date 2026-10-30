# Exact-target importance accuracy screen

Frozen before sampling. Two independent seeds951400001,951400002,16384 proposals
each, unchanged conditional_proposal.py settings qualified by the preflight.
Rebuild all1681 proposal-grid cells per fit. Training-only GP-TRAIN.json SHA256
8c328146cfe6e1956256af63bb3b39cfc0d27be4b8ea7b796d842240056b5576.
Use the raw81-dimensional compiled Stan target for every log-weight numerator;
proposal density is in the same raw unconstrained coordinates. Normalize weights
with logsumexp, no smoothing/clipping/truncation. Save every q,160functionals,
log target,log proposal,log weight,normalized weight and exact API counts.

This can run while independent references finish. Do not accept accuracy unless
the separately frozen reference is qualified and raw-audited. For each seed:
finite diagnostics, raw weight ESS>=1000,Pareto k<.7, maximum absolute mean error
<=.1 referenceSD, SD relative error<=.1, mean difference/combined MCSE<=4.
Self-normalized importance mean MCSE=sqrt(sum(w_i*(v_i-mean))^2), componentwise.
All160 quantities must pass for both seeds; no retries/extensions after failure.
No application value or predictive qualification follows from training accuracy.

Two concurrent BLAS1 workers, each300s/3GiB/128MiB,initial free disk>=1GiB.
Preserve failures. Runtime/source hashes before/after. This is an accuracy screen,
not a timing comparison; concurrent references prevent clean workflow timing.
Future precision-matched serial timings and predictive MCSE must be frozen
separately. No heldout labels transferred or scored.
