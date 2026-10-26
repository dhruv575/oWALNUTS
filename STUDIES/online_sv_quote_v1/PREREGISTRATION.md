# Preregistration: online_sv_quote_v1 (WP84)

Frozen 2026-10-25 on `wt/online-sv` (base `fa04c5b9`) before the first evidence cell.
`protocol.json` is the machine-readable copy and wins on any discrepancy. Ledger id
`WP84-ONLINE-SV-QUOTE-V1`.

## Question

The user's goal: an automated market maker whose quotes come from a Bayesian posterior that
must be refreshed each time a new observation arrives. WP84 asks: on a stochastic-volatility
model fed one return per tick, what is the tick-to-valid-posterior latency of oWALNUTS with
warm continuation and with a refit from scratch, against CmdStan 2.39.0 and nutpie 0.16.8
refits, at matched accuracy? And does the warm path stay calibrated over 100 ticks?

## What the continuation API supports (source reading at `fa04c5b9`)

`Sampler::start_session` / `SessionHandle` (`src/walnutpie/session.rs`,
`tests/continuation_session.rs`): one `adapt()` (warmup, once), then `draw(n)` chunks up to
a lifetime retained budget fixed at start, on **one immutable target of fixed dimension**
owned by the worker. Chunks expose the samples, the mass diagonal and the tuning read-only.
Identity/diagonal metrics only, no chain rescue. There is **no retarget**: no way to swap the
target, change its dimension, or inject positions, a step or a metric between advances.
`SV_MODEL_DESIGN.md` records the same constraint ("continuation currently promises one
immutable target").

So the warm arm is a **research-only retarget in the study harness, not in the library**
(`rust/src/main.rs`; no library change on this branch). Each tick it builds the new target
(n+1 observations, dimension+1), appends the new innovation z_new = 0 (its prior median) to
each chain's last position and the prior variance 1 to that chain's adapted diagonal metric,
and runs one single-chain public `Sampler` per chain in parallel threads with
`Metric::fixed_diagonal`, `Tuning::step_size(carried)`, `Adaptation::None`, `warmup(0)`,
`draws(K)`. **Re-adaptation policy: none.** Step and metric stay frozen from the tick-0 fit
(4 x 1,000/1,000 at defaults, reported but outside the latency statistics). Frozen tuning
keeps every retained transition an invariant kernel for its tick's posterior.

## Model and data

The `market_uncertainty_v1` SV target (`sv_prototype/target.py`) with one intercept and no
flow columns: y_i ~ t_5(beta, exp(h_i/2)), noncentred AR(1) log-vol with rho = 0.95 fixed,
priors mu ~ N(2 log 0.005, 1), log sigma ~ N(log 0.2, 0.5), beta ~ N(0, 0.002), z ~ N(0,1)
(the `ILLUSTRATIVE_PRIORS`). Dimension 3 + n. Data are **simulated** (`simulate.py`, seed
84084, mu = 2 log 0.005, sigma = 0.2, beta = 0, 1,100 returns). The repo's Deribit receipts
are not reused because no reuse licence is recorded. The Rust density matches `models/sv.stan`
through BridgeStan: lp offset spread 4e-12, gradient relative error 3e-14 at n = 250 and 1,001
(`run_cells.py check`, rerun on the box before the cells).

## Stream and quantities

N in {250, 1000}; T = 100 ticks; tick t conditions on the first N + t returns. The quantity is
the next-period log-vol h_next = mu + rho (h_last − mu) + sigma eps. eps is a fixed stream
`default_rng(840000+tick)`, shared by every arm, so all arms estimate the same functional.
Reported: the P5/P50/P95 of h_next, and a straddle quote proportional to E[exp(h_next/2)]
(Rao-Blackwellised; reported, not gated).

## Reference, validity, metrics

Reference per tick: oWALNUTS at defaults, 4 x 2,000/20,000, quantile MCSE from
`arviz.mcse(method="quantile")`. **Validity (primary, decision):** |q_arm − q_ref| <= 3 MCSE_ref
on all three quantiles, AND max rank R-hat over (mu, log sigma, h_last, h_next) <= 1.01, AND
zero retained divergences. Secondary (reported only, added because the primary bound ignores
the arm's own Monte Carlo error): the same rule with 3 sqrt(MCSE_ref² + MCSE_arm²). Chain
warnings are recorded for ref/refit. They are not available for warm, which runs four
single-chain samplers.

Arms (all on the lane's four cores): A warm K in {50, 200}; B oWALNUTS refit 4 x 1,000/1,000
defaults; C CmdStan defaults via cmdstanpy, 4 parallel chains; D nutpie defaults, cores = 4.
Latency is the wall per tick from target/data construction to draws in memory. For the Stan
arms it includes the data JSON, the process spawn and the CSV read (CmdStan), or `with_data`
(nutpie). Compilation is excluded. Metrics: median/p95 latency, the fraction of ticks
under 0.4 s and under 2 s, the validity rates, and the fraction of ticks that are both valid
and under the threshold. Drift (A): per tick, the fraction of the arm's h_next draws inside
the reference [P5, P95]. The bound is |mean over ticks − 0.90| <= 0.03 and
|mean(ticks 76–100) − mean(1–25)| <= 0.03, per seed. Also reported: coverage of the true
simulated h by the arm's 90 % interval.

Seeds: sampler 84001–84003; reference 849000+N; data 84084. 32 cells in the frozen order of
`protocol.json` (two references, then per N and seed: warm50, warm200, refit, cmdstan, nutpie),
sequential, never rerun. Failures are results.

## Predictions (written from WP78 per-gradient costs before any smoke run)

The prediction ranges P1–P6 are in `protocol.json` and are copied here unchanged:
P1 warm K=50 median 5–60 ms (N=250), 20–250 ms (N=1000), K=200 4x that; P2 refit 0.3–2 s /
1–8 s; P3 CmdStan 0.4–3 s / 1.5–10 s, nutpie 0.3–2 s / 1–8 s; **P4 primary validity <= 40 % for
every arm, so the real-time rule fails** (an estimate from 200–4,000 draws carries 2–20x the
reference's MCSE); P5 secondary validity >= 80 % refit arms, >= 60 % warm200, >= 40 % warm50;
P6 warm200 drift within bound on >= 5/6 (N, seed).

Smoke disclosure: a 3-tick WSL smoke of every arm (correctness only, not evidence) found
that a fatal `TargetError` on non-finite density aborted the oWALNUTS runs from uniform
starts. The harness now returns `TargetError::recoverable`, which rejects the proposal as
Stan does. The smoke confirmed that all six code paths and `analyze.py` run. No laptop timing
is used.

## Decision rule (what the README may claim)

"Real-time" only if, for some K, the warm arm is primary-valid AND under 0.4 s on >= 95 % of
the 300 ticks at N = 250, AND primary-valid AND under 2 s on >= 95 % at N = 1000, with drift
within bound on all three seeds at both N. Otherwise the README states only the measured
latency and validity.

## Execution

Lane 4 (cores 12–15) of the shared c7a.4xlarge, `taskset -c 12-15`, `RAYON_NUM_THREADS=4`,
`OMP_NUM_THREADS=1`, co-tenanted with three other lanes (shared L3 and memory bandwidth), so
walls are "pinned, co-tenanted"; validity and gradient counts are unaffected.
