# Fourfold blocked-path precision study

Status: implementation preparation; not launched.

The completed 1,000-warmup / 2,000-retained study left 14/24 fits flagged.
Thirteen windows flagged log_sigma, with worst bulk ESS 189.41 and worst scale
R-hat 1.03186. One additional window flagged a latent innovation. This motivates
a fixed fourfold budget study, rather than assuming predictive agreement proves
posterior fidelity.

Retain all 24 windows, four chains each, unchanged target and transitions,
block size 16, reference flags and diagnostic thresholds. Declare 4,000 warmup
and 8,000 retained sweeps per chain, with 96 fresh audited seeds and prior-center
initialization. Do not resume the previous chains. No retries, adaptive stopping,
window removal or budget extensions. This remains exposed-data development.

Each chain is limited to 1,200 seconds externally / 1,195 internally, eight
million density evaluations, 1 GiB RSS and 256 MiB output. Use 16 disjoint core
queues and the existing resource monitor. The outer bound is 19,200 seconds,
22 GiB RSS and 32 GiB sampled output cap; available disk imposes an additional
constraint, with at least 10 GiB required before launch and admission stopping
below 4 GiB. Expected retained arrays are about 1.6 GB total; outer byte limits
are not filesystem quotas. Preserve partial results on every failure.

Report every coordinate, full and 22-reference-passing summaries, signed
discrepancies and separate Monte Carlo errors. Compare with the full earlier
panel, including its failures. This experiment changes both warmup and retained
effort and cannot identify their individual contributions. Any pass is a
diagnostic result, not proof of exact convergence, unseen predictive value,
algorithm superiority or economic profitability.
