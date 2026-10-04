# Optional shared-log-volatility likelihood algebra

Static prototype only. Preserve mixed coordinates, block32 AR path, identical normalized priors and Student-t observation model. Replace only pm.StudentT likelihood expression with its normalized sum using the shared h_t term once per time. Gradients remain entirely PyTensor autodiff; no manual gradient or sampler change.

Validate actual archived five positions plus four deterministic broad-scale regimes against baseline compiled CFunc and independent JAX canonical+Jacobian density/gradient. Capture optimized graphs for both; only if graphs actually differ consider later bounded target-only timing. No parameter tuning sweep. Basic algebra may retain identical compiler graph or introduce poor finite-precision behavior; failures remain evidence. In particular exp(-h) and residual square can overflow even when a mathematically valid target exists, so nominal parity is not sufficient for deployment. Boundary tests against existing recoverable rejection policy must precede integration.

Queued correctness command: target/python-workflow-env/Scripts/python.exe target/mixed-target-optimization-v1/validate.py. Do not execute until parent releases timing hold. No MCMC or new RNG streams. All outputs remain isolated; no main study source edits or fresh-screen recipe changes.
