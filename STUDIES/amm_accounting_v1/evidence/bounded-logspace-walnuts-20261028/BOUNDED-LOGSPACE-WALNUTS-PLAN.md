# Fixed log-space WALNUTS follow-up

Separate nine-case panel following the preserved first WALNUTS panel, which
completed four fits and failed five on fatal target callbacks. Keep all original
slots, outputs, seeds and failures. This follow-up changes only the native
density/gradient evaluation and uses a newly declared seed interval. Do not
attribute any outcome solely to the implementation because seeds also differ.

Fixtures, physical initial state, chain counts, warmup/retained counts, tuning,
adaptation and diagnostic requirements are exactly BOUNDED-WALNUTS-PLAN.md.
The target is unchanged. Use bounded_logspace_native.py, which evaluates signed
standardized residuals directly, avoiding physical-scale reconstruction.
Require all 72 native parity cases, the captured-proposal check and four tail
checks, with exact source bindings, before launch. Arbitrary NaNs remain fatal.

The sole explicit -infinity branch bounds mathematical log density below the
negative double range: write log density <= U - beta^2/(2*.002^2), dropping
nonpositive quadratic priors and Student-t residual terms. If U is finite and
<=MAX_FLOAT while the log penalty exceeds log(MAX_FLOAT)+log(4), reject the
numerically negligible proposal. This is numerical negative overflow, not a
claim of zero mathematical support. Positive-tail fixtures independently evaluate
to about -4.85e873 at 90-digit precision, below the double range. Finite-gradient
overflow without that bound remains an explicit error, not silent rejection.

Fit j sample seed 398140000+16*j; reserve/audit all 144 integers. No changed
initialization, smaller step size, replacement seeds or extra budget after
inspection. Same disjoint 4-core groups, per-fit 900seconds/4GiB/512MiB and outer
2760seconds/18GiB/3GiB; require 4GiB free disk. Preserve all draws, event phases,
metadata, sources and resource logs, including failures. Report recoverable
target-failure counts, not just retained divergences. Comparisons to frozen
qualified references must hash-check inputs. This is synthetic implementation
validation, not market prediction or economic evidence.
