# Post-screen banana precision/native follow-up

This follow-up was specified after inspecting the original held-out screen.
The original result is preserved: WALNUTS passed 8/8 ladders on the banana,
NUTS 0/8. At 3,000 draws all NUTS estimates were inside the absolute-error
bands and all runs passed conventional diagnostics; they failed the tighter
MCSE criterion by factors 1.012-1.167. This is a precision lead, not evidence
that NUTS sampled a wrong distribution. WALNUTS used more target calls despite
lower Python-path runtime, motivating a native-interface cross-check.

Fresh seeds, same banana and accuracy gates. Four frozen configurations:
WALNUTS .99, original diagonal NUTS .99, low-rank NUTS .99, and NUTS .99 with
draw-based rather than gradient-based mass adaptation. Eight seeds each and
independent budgets 3,000/6,000/12,000 draws per chain, 750 warmup, four sequential
chains, identical dispersed starts: 96 planned fits. Every budget runs. Charge
unsuccessful lower budgets when reporting a first-pass ladder; show fixed-budget
results and total/setup/sampler time separately. No favorable baseline is omitted.

Both engines call the identical Numba analytic density through their native C
ABIs, without per-gradient Python dispatch. The NUTS adapter uses the pinned
installed CompiledPyMCModel interface with an identity expansion callback; it
does not fit a different PyMC model. ABI values/gradients/counters are tested
against the original density, and all four adapters get an independent standard
normal moment test. Report this interface dependency and all callback failures.

Native construction compiles both adapters before either method is timed. Its
common setup cost is reported and charged to both; this is a conservative common
benchmark setup rather than optimized production setup for either engine.
Native counters share one sequential worker and cannot be used with parallel
chains without additional synchronization. Nonfinite callbacks are recorded.

Seed base 675000000, config stride 100000, replicate stride 1000, budget offsets
0/1/2; tests 685000000+. Up to 12 one-core jobs, 120 seconds, 1 GiB RSS and
20 MiB per fit. No model, gate, original selection or library default changes.
This is a selected-target exploratory follow-up, not independent validation of
a broad geometry class. The banana has an exact Gaussian reparameterization;
even a positive outcome does not establish an application advantage.
