# Independent literal-reference readiness

Status: reviewed design, not executed. This check follows the completed T250
development fixture and precedes any market sampler-performance campaign.
`literal_reference.py` implements the bounded run and full-trace retention.
Four local tests cover manifest drift, fixed budgets, named-axis extraction and
the supervisor invocation contract. All four plus the inherited monitor's live
clean-exit/process-drain test pass in the pinned AWS runtime. Review corrected a
phase/core mapping mismatch before sampling; the first test-discovery invocation
also failed because the shell expanded a wildcard. Both failed and passing logs
are preserved in `evidence/literal-reference-readiness-20261028/`.
These are runner checks only; compilation and sampling for this new entry point
have not yet been exercised. Runtime prefix, package versions and binary hashes
are checked against the bound runtime inventory. A frozen path/hash manifest,
seed audit, runtime binding and available four-core allocation are still needed.
Do not compete with E72's four reserved worker groups. Run under the existing
resource supervisor only after a group is released and its ownership drains,
or after the campaign terminates. Preserve E72's resource caps unchanged.

## Target and evidence bindings

Use exactly `numpy.resize([.001,-.002,.0005,0.,.003],250)` and the already
verified price-only Stan model in `independent_sv_reference_preflight_v1`.
Fixed rho=.95, Student-t degrees of freedom=5, mu prior N(2 log(.005),1),
log_sigma prior N(log(.2),.5), beta prior N(0,.002), and 250 independent
standard-normal innovations. The likelihood uses exp(h/2) as t scale.
Bind the Stan source, adapter, compiler capture, BridgeStan SDK Makefile,
runtime inventory and literal data by SHA-256 before compiling. Verify the
fixture and priors against development.py and sentinel_adapter.stan_data.

Retain all eight existing specialist chains without rerunning or selecting
them. Bind their original metadata and array hashes. The observed development
results motivated this check; it is not untouched confirmation of superiority.

## Fixed independent run

Use the existing validated nutpie/BridgeStan configuration and four chains,
2,000 adaptation iterations and 4,000 retained draws per chain. Preserve warmup,
divergences, full innovations and the four compact endpoints. Reserve and audit
sampling and model-initialization seeds before execution; no seed is assigned
by this document. Capture the compiled shared library and compiler invocation.

One attempt, four cores, 4 GiB sampled process-tree RSS, 512 MiB output and
900 seconds including compilation. The outer supervisor must kill and drain
owned descendants at the cap. No automatic retries, cap extensions or replacement
seeds. Missing output and timeout remain explicit. A later larger reference
would be a separately declared experiment preserving this attempt.

## Comparisons and interpretation

Report mu, log_sigma, beta, h_last and all 250 innovation diagnostics, including
rank Rhat, bulk/tail ESS, per-chain divergences and mean MCSE. Report posterior
means, standard deviations and 5/50/95 percent quantiles for all three methods.
Do not silently pool chains from different algorithms.

Use the unchanged predictive evaluator at all three previously fixed labels
[-.005,0,.005], with its GH64/128 check. Report log(mean predictive density),
PIT and their MCSE for each method. Preserve all six specialist/reference
contrasts. Log-density MCSE uses stabilized density means, not mean log density.
Show differences and each method's uncertainty separately; don't combine MCSE
as independent without checking seed provenance and the sampling construction.

Diagnostics are necessary evidence, not proof of exact posterior draws. If the
reference has divergences, Rhat above 1.01 or bulk/tail ESS below 400 for any
coordinate, flag the reference as unresolved and retain all comparisons as
descriptive. These readiness flags are declared before reference sampling and
must not erase unfavorable rows. No universal equivalence tolerance or
superiority verdict is inferred from overlap. Large discrepancies require
target/density and sampler investigation before a performance campaign.

This literal check cannot establish calibration, performance on market windows,
whole-path fidelity, decision value, or profitability. Those remain separate
research gates. Hardware/runtime differences prohibit using the existing local
specialist timings against AWS reference timings as a speed benchmark.
