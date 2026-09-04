# posteriordb benchmark v6 — preregistration (WP35)

Frozen 2026-09-04 before the first evidence cell. The machine-readable
protocol is `protocol.json`. The source commit under test is `aa4510f`, the
merged 0.2.0 tree through WP34. Seeds 90101–90103 were verified unused by an
exact whole-number search over the research record and source tree before this
freeze.

## Question

`posteriordb_bench_v5` is the current release headline, but it predates the
last sampler-default change. WP33 made
`ChainRescueConfig::restart_from_best()` the default for multi-chain identity
and diagonal runs after a preregistered eight-model decision study. Does the
complete post-WP33 default remain broad, efficient and reference-consistent on
the full 17-model benchmark, and what does the rescue actually do on fresh
starts?

This is a validation and characterisation of an already-made default change.
It does not decide the change and cannot silently reverse it.

## Change under test

The only sampler change since v5 is
`sampler::DEFAULT_CHAIN_RESCUE = ChainRescueConfig::restart_from_best()`.
`Adaptation::default()` installs it for this four-chain adapted-diagonal run.
At each completed slow metric window, a chain whose step is below 0.1 times
the chains' median step, or whose median selected-state log density is more
than three within-chain IQRs below the chains' median, is restarted from the
largest-step non-outlier chain's window with that chain's metric, step and
dual-averaging state. Retained transitions are unchanged. Every boundary
decision is recorded as a `ChainRescueUpdate`.

The retained kernel revision, momentum-sum U-turn rule, Stan diagonal-metric
regularisation, warmup-only one-sided exhaustion rule, eight refinement
levels, depth 10, `delta = 1`, target acceptance 0.8, cached initial
evaluation and competitors are unchanged from v5.

## Protocol

The v5 protocol is repeated:

- posteriordb commit `28f8d3d`, the same 17 posteriors and reference-draw
  parameter sets;
- arms in fixed order: `owalnuts-da`, CmdStan 2.39.0, nutpie 0.16.8;
- 4 chains, 1,000 warmup and 1,000 retained transitions;
- fresh seeds 90101, 90102 and 90103, shared by arm;
- oWALNUTS at `Sampler` defaults, adapted diagonal metric, four threads,
  `Init::uniform()` and exact worst-case admission;
- CmdStan and nutpie at their defaults;
- rank R-hat <= 1.01, bulk and tail ESS >= 400 on every reference parameter,
  zero retained divergences, finite draws and no sampler error;
- ArviZ 0.23.4 estimators and reference-mean z scores;
- 2,700-second cell timeout, strictly sequential model / arm / seed order;
- no result-driven reruns or tuning.

The side check repeats Neal's 10-D funnel at the sampler defaults with starts
`omega = {-3,-1,1,3}`, 4 x 2,000 warmup / 20,000 retained per seed, and the
MCSE z of `P(omega < -5)` against the exact 0.0478.

## Added telemetry

For every oWALNUTS chain the raw cell records all rescue boundary updates:
window and transition, chain, window length, pre-boundary step, median and IQR
of log density, and outcome. Restart outcomes additionally record source
chain, criterion, source position and post-restart step. Analysis reports
rescues by criterion, model, seed and gate outcome, and names every restart.

The reference-agreement check is primary rather than decorative: every passing
oWALNUTS cell's maximum absolute z is checked against 4. A rescue may remove a
chain from a second mode and make R-hat blind to that mode; the telemetry and z
table must make that intervention visible.

## Predictions fixed before execution

| | prediction | reference |
|---|---|---|
| P1 | oWALNUTS passes at least **42/51** cells | v5, before rescue was default: 42 |
| P2 | no passing oWALNUTS cell has **max \|z\| > 4** | v5 agreement flag; WP33 had none above 3.5 |
| P3 | over the fixed 16-model set excluding `arma11`, geomean minimum bulk ESS/gradient versus CmdStan is **>= 0.75** | v5: 0.822 |
| P4 | over that fixed set, geomean wall/gradient versus CmdStan is **<= 1.0** | v5 all-model figure: 0.801 |
| P5 | geomean minimum bulk ESS/s versus nutpie is **>= 1.5** over models complete on both sides | v5: 3.085 |
| P6 | funnel tail-mass **\|z\| <= 2 on every seed** | v5: +1.02, -0.05, +0.93; WP33 restart: +0.94, -0.77, -1.02 |
| P7 | no frozen oWALNUTS chain; rescue telemetry explains material gate changes from v5 | descriptive because seeds differ |

P3 and P4 use the 16 model names frozen in `protocol.json`; the set is not
selected after seeing which CmdStan cells pass. P5 uses complete cells because
nutpie can fail to return a cell on `lotka_volterra`.

## Release rule

This run replaces v5 as the breadth headline for the current defaults if all
153 posteriordb cells are present, P1–P4 and P6 hold, and all passing
oWALNUTS cells meet P2. P5 and P7 are reported, not release gates. A failed
prediction is printed beside the numbers. It does not reverse WP33; any
default change requires a separate preregistered decision study.

## Execution rules

All cells are reported. Failures and timeouts are results. Nothing is tuned
after a result is observed. A driver crash may be relaunched; an interrupted
cell lacking a completed artifact may be rerun from scratch with the same
seed, and the deviation is recorded. Raw constrained draws are checksummed
and left uncommitted; cell metrics, summary, tables, logs and manifests are
committed.
