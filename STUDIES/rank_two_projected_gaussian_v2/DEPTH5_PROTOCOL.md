# Final depth-5 synthetic intervention

Frozen before execution on 2026-08-30.

Seeds 76001--76004. The sole sampler change from depth 4 is maximum depth 5.
Target, zero starts, pooled rank-two adaptation, warmup=180, retained=300,
windows, step search, and baseline are unchanged. Preflight must start zero
target callbacks.

Acceptance requires, for adaptive chains:

* maximum-depth rate <=1% both aggregate and per seed;
* every transition finite and nondivergent;
* every coordinate retained mean has absolute value <=0.75 and retained
  variance lies in [0.35, 1.65] times its exact marginal variance;
* geometric ESJD and lag-one inefficiency improvements over baseline >=1.05.

Target calls and leaves are reported against the depth-4 artifact. Passing may
freeze, but never execute, a separate T=1000 pilot. Its depth must be selected
from T=1000-specific preflight, cap telemetry, and resource bounds rather than
inherited automatically from this fixture.
