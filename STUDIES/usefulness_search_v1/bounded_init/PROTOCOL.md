# Bounded gradient-informed initial metric: mechanism screen

Frozen 2026-10-30 on parent 2dbdc651 before candidate runs. WP94's unbounded
metric reduced warmup work but introduced failures and hid a Lotka trap from the
step-ratio guard; it remains rejected. This screen tests a different bounded
configuration of the existing research-only feature, not a library default change.

Candidate mass_i = clamp(abs(start_gradient_i), 0.1, 1000). This bounds the initial
metric condition number by 10000 and avoids vanishing-gradient floors while
retaining useful scaling on stiff SV coordinates. Bounds are a heuristic, not
unit-invariant or theoretically optimal; no grid search or selection from results.
Keep the shipped restart guard and all other adaptation/kernel settings unchanged.
Controls: shipped defaults and original unbounded gradient scaling. Use one
research-feature binary for all arms; no source change to the sampler itself.

Mechanism preflight: default/custom-noop exact samples and work; clamped initial
masses equal clipped unbounded masses coordinatewise on identical starts; existing
grad_init_metric and kernel fingerprint tests pass. Exclude preflight seeds
939990001/2 from evidence. Seed scan found no integer uses of evidence blocks in
tracked study protocol/code documents before freezing (raw floating-point digit
substrings are not seed collisions).

PDB screen: hudson_lynx_hare-lotka_volterra,
bball_drive_event_0-hmm_drive_0, mcycle_gp-accel_gp,
radon_all-radon_hierarchical_intercept_centered. Four seeds 939100001--4,
three arms defaults/gradinit/bounded: 48 cells. Previous failure models and gain
models deliberately retained; these are exposed targets, fresh stochastic seeds.
Four chains, 1000 warmup/1000 retained, default best-of-16 starts, four threads.

SV screen: archived WP94 data, N=250, eight seeds 939200001--8, same three arms,
four chains 1000/1000: 24 cells. Preserve telemetry and apply the existing frozen
SV census/anchor. Funnel: fixed starts omega=-3,-1,1,3 with x=0, seeds 939300001/2,
diag/gradinit/bounded, 2000 warmup/20000 retained: six cells. Known omega<-5
probability 0.04779035227; report chain-aware MCSE and require |z|<=3 per
candidate seed; this small control is not sufficient to prove absence of bias.

78 cells, randomized manifest order, three workers on disjoint four-core groups.
Each cell bounded by 600 seconds, 2 GiB RSS and 64 MiB sampled output; processes
must drain. Admit only with 1 GiB root and 4 GiB tmpfs free. No failed-cell retries.

Screen gates: bounded must not lose per-model diagnostic pass counts versus
defaults (R-hat<=1.01, bulk/tail ESS>=400, zero retained divergences, finite draws);
no new trapped SV chains versus defaults; and the funnel check above. Record
all warnings and guard firings. Efficiency: per-model median paired minimum bulk
ESS / all target calls, then geometric mean over four PDB targets >=1.10 versus
defaults with no model <0.90. Report warmup calls and wall time separately. Also
require SV median warmup calls <=0.90 of default. Missing/failed cells fail gates.
Comparison with unbounded scaling explains mechanism but cannot rescue failure
against the current default. A pass motivates broader untouched-model/seed
confirmation only; it does not satisfy the overall goal or authorize promotion.
