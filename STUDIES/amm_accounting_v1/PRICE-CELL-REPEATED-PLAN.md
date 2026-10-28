# Repeated shifted-window confirmation design

Development evidence selected 1,024 warm draws per chain as a candidate
budget; retrospective prefixes do not count as confirmation. Freeze this
design before generating the new draws.

Four paths: the two T=250 static fixtures (width .001 and .00001), each with
two independently seeded continuation paths from the same saved static fit.
Shared initial states mean these are conditional replications, not independent
posterior initializations. Each path takes three consecutive one-cell shifts,
retaining its own last warm state between updates. Warm sessions use 1,024
draws per chain, four chains, no discard, no new adaptation and the already
declared tuning/remap rules. All three hyperparameters and both latent blocks
remain part of the diagnostics.

Append cells from .003*sin(.17*t)+.001*sin(.61*t) at t=250,251,252 using
the fixed nearest-width partition. Initial boundary price stays zero for both
warm and cold methods at every update. This explicit synthetic conditioning
does not model a historical rolling boundary. The first appended observation
matches the earlier development update, so fresh seeds address Monte Carlo
repeatability, not independent data generalization.

Each update gets a fresh NUTS reference: 2,000 warmup, 4,000 retained,
four chains, target_accept=.9, maxdepth10, no low-rank/transform adaptation.
Use warm base seed 398132000+100*path. Resident calls use four consecutive
chain seeds per update; reference sampling seeds base+40+2*update and model
seeds one higher. Audit the reserved 400-integer range before launch.

Four disjoint four-core jobs, each bounded to 900 seconds, 4GiB RSS and
768MiB output; outer limits 960 seconds, 18GiB RSS and 3.25GiB output.
Require at least 4GiB free disk at admission. Preserve all twelve method
pairs, traces, input/source hashes, diagnostics, sampler warnings and actual
phase timings, including startup/compilation separately. Do not replace failed
paths or extend budgets after seeing results.

Assess every coordinate using the existing Rhat<=1.01, bulk/tail ESS>=400,
zero retained-divergence criteria; report depth hits separately. Re-evaluate
the same bounded CDFs with quadrature checks. A useful result needs reliability
across repeated updates and actual measured costs, not only mean agreement or
the passing average of a failed path. Market validation and economic goals
remain separate and are not satisfied by this study.
