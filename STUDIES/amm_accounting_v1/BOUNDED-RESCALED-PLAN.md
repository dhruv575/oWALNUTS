# Fixed exact-coordinate-change stress panel

Exploratory follow-up to the frozen nine-case bounded-scale panel. Do not replace
or erase its failures. Three fits, T=12, y exactly zero, caps .5/1/2, rho .95.
The target is unchanged: beta=exp(mean(h)/2)*b with its explicit Jacobian and
the original Gaussian physical-beta prior. Require 72-case independent Stan
autodiff parity before launch. This is a geometry experiment, not an independent
posterior reference or a new scientific prior.

Four NUTS chains, 2,000 warmup and 4,000 retained draws per fit, target_accept .9,
maxdepth10, no low-rank or transform adaptation. Same central physical start as
the original NUTS panel: mu=2log(.005), sigma=.2, beta=0, z=0 (hence b=0).
Fit j uses sampler seed398136000+16*j and model seed+1; reserve all48 integers.
These are new declared seeds; no restarts or tuning extensions on failure.

Run three fits concurrently on disjoint four-core groups. Each has600seconds,
4GiB RSS and128MiB output limits; outer660seconds,14GiB RSS and512MiB output.
Require1GiB free disk. Preserve complete warmup/retained traces, source bindings,
seed audit and supervision. Admission additionally verifies the completed parity
report's source bindings, not merely its filename.

Report physical mu,log_sigma,beta,z diagnostics with Rhat<=1.01 and bulk/tail
ESS>=400; also report b diagnostics, divergence/depth events and sampling time.
Do not count transformed-coordinate diagnostics as a substitute for physical
diagnostics. No comparison to the failed original runs qualifies a reference,
even if new diagnostics pass. Inspect chain-specific h and cap concentration
before choosing the next independent-reference design.
